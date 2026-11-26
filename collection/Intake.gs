const SHEET_HEADERS = {
  Raw_Observations: ['Observation_ID', 'Payload_SHA256', 'Received_At_UTC', 'Consent_Version', 'Observation_JSON'],
  Reviewed_Observations: ['Observation_ID', 'Reviewed_At_UTC', 'Publication_Approved', 'Sanitized_Observation_JSON'],
  Rejected_Observations: ['Observation_ID', 'Reviewed_At_UTC', 'Reason_Code'],
  Vehicle_Aliases: ['Submitted_Make', 'Submitted_Model', 'Canonical_Make', 'Canonical_Model', 'Scope'],
  Processing_Log: ['Timestamp_UTC', 'Run_ID', 'Status', 'Accepted_Count', 'Rejected_Count', 'Unmatched_Count'],
  Data_Dictionary: ['Field', 'Meaning'],
};
const DICTIONARY = {
  schemaVersion: '1. Observation schema version.',
  id: 'Stable random UUID v4 for one observation.',
  observedAt: 'Client observation time in canonical UTC ISO 8601. Self-reported.',
  year: 'Model year, 1886 through current UTC year + 2.',
  make: 'Required manufacturer, up to 70 characters.',
  model: 'Required model, up to 90 characters.',
  condition: 'new or used.',
  priceCents: 'Integer USD cents, 1 through 1000000000.',
  type: 'asking, quote, or purchase (reported).',
  scope: 'vehicle, out_the_door (including taxes and fees), or unknown.',
  source: 'contributed. User-contributed provenance.',
  verification: 'unverified. Intake validation does not verify a price or sale.',
  catalogId: 'Optional shopper-context catalog configuration ID. Confirm association during review.',
  trim: 'Optional trim, up to 90 characters.',
  mileage: 'Optional integer odometer miles, 0 through 2000000.',
  powertrain: 'Optional description, up to 60 characters.',
  drivetrain: 'Optional description, up to 40 characters.',
  zip: 'Optional vehicle ZIP, five digits. Treat as text.',
  sellerType: 'Optional dealer, private, or other.',
  listingUrl: 'Optional HTTPS URL stripped of query and fragment. Inspect path before reuse.',
  vehicleNotes: 'Optional vehicle-only text, up to 500 characters. Review for identifiers.',
  nickname: 'Optional unverified pseudonym, up to 40 characters. Do not publish by default.',
  Received_At_UTC: 'Server receipt time in UTC.',
  Consent_Version: 'Intake consent text version (1).',
  Payload_SHA256: 'Hex digest of normalized submitted JSON for idempotent retries.',
};

function doGet() {
  return HtmlService.createHtmlOutputFromFile('Intake').setTitle('Car Shopping Guide contribution')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

function digest_(text) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, text, Utilities.Charset.UTF_8)
    .map(byte => (byte & 255).toString(16).padStart(2, '0')).join('');
}

function matchesDigest_(actual, expected) {
  if (!expected || actual.length !== expected.length) return false;
  let difference = 0;
  for (let index = 0; index < actual.length; index++) {
    difference |= actual.charCodeAt(index) ^ expected.charCodeAt(index);
  }
  return difference === 0;
}

function getCollection_() {
  const id = PropertiesService.getScriptProperties().getProperty('SPREADSHEET_ID');
  if (!id) throw Error('Collection is unavailable.');
  return SpreadsheetApp.openById(id);
}

// A trailing underscore keeps this owner setup function inaccessible to google.script.run.
function initializeCollection_() {
  const book = getCollection_();
  for (const [name, headers] of Object.entries(SHEET_HEADERS)) {
    const sheet = book.getSheetByName(name) || book.insertSheet(name);
    const row = sheet.getRange(1, 1, 1, headers.length);
    if (sheet.getLastRow() === 0) {
      row.setValues([headers]);
      sheet.setFrozenRows(1);
    } else if (JSON.stringify(row.getValues()[0]) !== JSON.stringify(headers)) {
      throw Error('Unexpected headers in ' + name);
    }
  }
  const dictionary = book.getSheetByName('Data_Dictionary');
  const rows = Object.entries(DICTIONARY);
  if (dictionary.getLastRow() === 1) dictionary.getRange(2, 1, rows.length, 2).setValues(rows);
}

function submitObservation(payload, inviteCode, consent) {
  if (consent !== true) return { status: 'rejected', message: 'Consent is required.' };
  if (typeof payload !== 'string' || payload.length > 8000
      || typeof inviteCode !== 'string' || !/^[a-f0-9]{48}$/.test(inviteCode)) {
    return { status: 'rejected', message: 'Check the payload size and pilot invite code.' };
  }
  const properties = PropertiesService.getScriptProperties();
  if (!matchesDigest_(digest_(inviteCode), properties.getProperty('INVITE_SHA256'))) {
    return { status: 'rejected', message: 'Pilot invite code is invalid or collection is closed.' };
  }
  let record;
  try {
    const records = decodeObservations_(payload, { shared: true });
    if (records.length !== 1) throw Error('Submit one observation at a time.');
    record = records[0];
  } catch {
    return { status: 'rejected', message: 'Invalid observation. Use the sanitized export from the guide.' };
  }

  const json = JSON.stringify(record);
  const fingerprint = digest_(json);
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(4000)) return { status: 'retry', message: 'Collection is busy. Retry the same record.' };
  try {
    // Recheck revocation after waiting for the lock.
    if (!matchesDigest_(digest_(inviteCode), properties.getProperty('INVITE_SHA256'))) {
      return { status: 'rejected', message: 'Pilot invite code is invalid or collection is closed.' };
    }
    const sheet = getCollection_().getSheetByName('Raw_Observations');
    if (!sheet || sheet.getRange(1, 1).getValue() !== 'Observation_ID') throw Error('Intake setup missing.');
    const last = sheet.getLastRow();
    if (last > 1) {
      const existing = sheet.getRange(2, 1, last - 1, 1).createTextFinder(record.id)
        .matchEntireCell(true).findNext();
      if (existing) {
        return sheet.getRange(existing.getRow(), 2).getValue() === fingerprint
          ? { status: 'duplicate', id: record.id }
          : { status: 'conflict', message: 'This observation ID already has different data. Ask the project owner before resubmitting.' };
      }
    }
    const timestamp = new Date().toISOString();
    const day = timestamp.slice(0, 10);
    const [previousDay, previousCount] = (properties.getProperty('DAILY_WRITES') || '').split('/');
    const used = previousDay === day ? Number(previousCount) : 0;
    if (used >= 50 || last >= 5001) {
      return { status: 'retry', message: 'Pilot capacity reached. Keep your copy and try later or contact the project owner.' };
    }
    properties.setProperty('DAILY_WRITES', day + '/' + (used + 1));
    // JSON begins with "{". No untrusted value is written as a standalone cell.
    // UUID, digest, timestamp and consent version are constrained literals.
    sheet.appendRow([record.id, fingerprint, timestamp, 'v1', json]);
    SpreadsheetApp.flush();
    return { status: 'received', id: record.id };
  } catch {
    return { status: 'retry', message: 'Delivery could not be confirmed. Retry with the same observation ID and data.' };
  } finally {
    lock.releaseLock();
  }
}
