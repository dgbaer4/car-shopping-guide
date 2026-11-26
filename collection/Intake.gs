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
  Consent_Version: 'Intake consent text version (2 for direct sharing).',
  Payload_SHA256: 'Hex digest of normalized submitted JSON for idempotent retries.',
};

function doGet() {
  return renderIntake_('');
}

function doPost(event) {
  const inputs = event?.parameters?.payload;
  if (inputs?.length === 1 && typeof inputs[0] === 'string' && inputs[0].length <= 8000) {
    try {
      const records = decodeObservations_(inputs[0], { shared: true });
      if (records.length === 1) return renderIntake_(encodeObservations_(records, { shared: true }));
    } catch {
      // Invalid handoffs render the no-observation screen without echoing user input.
    }
  }
  return renderIntake_('');
}

function renderIntake_(payload) {
  const template = HtmlService.createTemplateFromFile('Intake');
  template.payload = payload;
  return template.evaluate().setTitle('Car Shopping Guide contribution')
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

const HOUR = 3600000;
const DAY = 24 * HOUR;
const HEX_SECRET = /^[a-f0-9]{64}$/;
const DEVICE_TOKEN = /^([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})\.[a-f0-9]{64}$/;
const CLOSED = { status: 'closed', message: 'Shared collection is paused. Your local tracker is still available.' };
const BUSY = { status: 'retry', message: 'Collection is busy. Retry the same observation.' };
const UNAUTHORIZED = { status: 'unauthorized', message: 'Device authorization is unavailable. Enroll again or contact the project owner.' };

function hmac_(message, key) {
  // The hex string itself is the HMAC key. The owner helper uses the same UTF-8 encoding.
  return Utilities.computeHmacSha256Signature(message, key, Utilities.Charset.UTF_8)
    .map(byte => (byte & 255).toString(16).padStart(2, '0')).join('');
}

function readState_(properties, key) {
  return JSON.parse(properties.getProperty(key) || 'null');
}

function enrollDevice(invitation, remember, nonce) {
  if (typeof invitation !== 'string' || invitation.length > 40 || typeof nonce !== 'string' || !HEX_SECRET.test(nonce)) {
    return { status: 'rejected', message: 'Enter the invitation supplied by the project owner.' };
  }
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(500)) return BUSY;
  try {
    const properties = PropertiesService.getScriptProperties();
    if (properties.getProperty('INTAKE_OPEN') !== 'true') return CLOSED;
    const key = properties.getProperty('TOKEN_KEY');
    const invite = readState_(properties, 'INVITATION');
    const now = Date.now();
    if (!HEX_SECRET.test(key || '') || !invite || !HEX_SECRET.test(invite.digest)
        || !(Date.parse(invite.expiresAt) > now)) {
      return { status: 'rejected', message: 'Enrollment is closed. Ask the project owner for a current invitation.' };
    }
    const hour = Math.floor(now / HOUR);
    const previous = readState_(properties, 'ENROLLMENT_LIMITS');
    const counts = previous?.invitation === invite.digest ? previous
      : { invitation: invite.digest, failures: 0, enrolled: 0 };
    if (counts.hour !== hour) Object.assign(counts, { hour, attempts: 0 });
    if (counts.attempts >= 8 || counts.failures >= 24 || counts.enrolled >= 30) {
      return { status: 'limited', message: 'Enrollment is temporarily unavailable. Try later or contact the project owner.' };
    }
    counts.attempts++;
    const supplied = hmac_('invite:' + invitation.trim().toLowerCase(), key);
    if (!matchesDigest_(supplied, invite.digest)) {
      counts.failures++;
      properties.setProperty('ENROLLMENT_LIMITS', JSON.stringify(counts));
      return { status: 'rejected', message: 'Invitation was not accepted. Check with the project owner.' };
    }
    counts.enrolled++;
    properties.setProperty('ENROLLMENT_LIMITS', JSON.stringify(counts));
    const id = Utilities.getUuid().toLowerCase();
    const token = id + '.' + hmac_('device:' + id + ':' + nonce, key);
    const remembered = remember === true;
    const expiresAt = now + (remembered ? 30 * DAY : 12 * HOUR);
    properties.setProperty('DEVICE_' + id, JSON.stringify({
      digest: digest_(token), remembered, expiresAt, hardExpiry: now + (remembered ? 90 * DAY : 12 * HOUR),
    }));
    return { status: 'enrolled', id, token, expiresAt };
  } catch {
    return { status: 'retry', message: 'Enrollment could not be confirmed. Try again or contact the project owner.' };
  } finally {
    lock.releaseLock();
  }
}

function submitObservation(payload, token, consent) {
  if (consent !== true) return { status: 'rejected', message: 'Consent is required.' };
  if (typeof payload !== 'string' || payload.length > 8000) {
    return { status: 'rejected', message: 'Check the contribution size.' };
  }
  const match = typeof token === 'string' && DEVICE_TOKEN.exec(token);
  if (!match) return UNAUTHORIZED;
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return BUSY;
  try {
    const properties = PropertiesService.getScriptProperties();
    if (properties.getProperty('INTAKE_OPEN') !== 'true') return CLOSED;
    const id = match[1];
    const deviceKey = 'DEVICE_' + id;
    const device = readState_(properties, deviceKey);
    const now = Date.now();
    if (!device || properties.getProperty('REVOKED_' + id) || !(device.expiresAt > now)
        || !(device.hardExpiry > now) || !matchesDigest_(digest_(token), device.digest)) return UNAUTHORIZED;
    const hour = Math.floor(now / HOUR);
    if (device.hour !== hour) Object.assign(device, { hour, attempts: 0 });
    if (device.attempts >= 20) return { status: 'limited', message: 'Device request limit reached. Retry later.' };
    device.attempts++;
    properties.setProperty(deviceKey, JSON.stringify(device));

    let record;
    try {
      const records = decodeObservations_(payload, { shared: true });
      if (records.length !== 1) throw Error('Submit one observation at a time.');
      record = records[0];
    } catch {
      return { status: 'rejected', message: 'Invalid observation. Return to the tracker and review the contribution.' };
    }

    const json = JSON.stringify(record);
    const fingerprint = digest_(json);
    const sheet = getCollection_().getSheetByName('Raw_Observations');
    if (!sheet || sheet.getRange(1, 1).getValue() !== 'Observation_ID') throw Error('Intake setup missing.');
    function receipt(status, receivedAt) {
      if (device.remembered) {
        device.expiresAt = Math.min(now + 30 * DAY, device.hardExpiry);
        properties.setProperty(deviceKey, JSON.stringify(device));
      }
      return { status, id: record.id, receivedAt, expiresAt: device.expiresAt };
    }
    const last = sheet.getLastRow();
    if (last > 1) {
      const existing = sheet.getRange(2, 1, last - 1, 1).createTextFinder(record.id)
        .matchEntireCell(true).findNext();
      if (existing) {
        const savedTime = sheet.getRange(existing.getRow(), 3).getValue();
        return sheet.getRange(existing.getRow(), 2).getValue() === fingerprint
          ? receipt('duplicate', new Date(savedTime).toISOString())
          : { status: 'conflict', message: 'This observation ID already has different data. Contact the project owner.' };
      }
    }
    const timestamp = new Date(now).toISOString();
    const day = timestamp.slice(0, 10);
    const [previousDay, previousCount] = (properties.getProperty('DAILY_WRITES') || '').split('/');
    const used = previousDay === day ? Number(previousCount) : 0;
    const deviceWrites = device.day === day ? device.writes : 0;
    if (used >= 50 || deviceWrites >= 10 || last >= 5001) {
      return { status: 'limited', message: 'Pilot write limit reached. Keep your copy and retry later or contact the project owner.' };
    }
    properties.setProperty('DAILY_WRITES', day + '/' + (used + 1));
    Object.assign(device, { day, writes: deviceWrites + 1 });
    properties.setProperty(deviceKey, JSON.stringify(device));
    // Only constrained literals and JSON are written as standalone cell values.
    sheet.appendRow([record.id, fingerprint, timestamp, 'v2', json]);
    SpreadsheetApp.flush();
    return receipt('received', timestamp);
  } catch {
    return { status: 'retry', message: 'Delivery could not be confirmed. Retry with the same observation ID and data.' };
  } finally {
    lock.releaseLock();
  }
}
