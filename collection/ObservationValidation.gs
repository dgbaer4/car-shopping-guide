// Generated from engine/observations.mjs.
const observationTypes = {
  asking: 'Advertised asking price',
  quote: 'Dealer or seller quote',
  purchase: 'Reported completed purchase',
};

const priceScopes = {
  vehicle: 'Vehicle only',
  out_the_door: 'Out the door (including taxes and fees)',
  unknown: 'Price scope unknown',
};

const provenance = {
  market: '📊 Published market pricing',
  msrp: '🏭 Manufacturer MSRP',
  contributed: '👥 User-contributed observation',
  quote: '🏷️ Dealer or seller quote',
  purchase: '🧾 Reported completed purchase',
};

const textLimits = {
  make: 70, model: 90, trim: 90, powertrain: 60, drivetrain: 40,
  nickname: 40, vehicleNotes: 500, catalogId: 100,
};
const idPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const interests = ['GOOD', 'POSSIBLE', 'DON’T THINK SO'];

function check_(test, message) {
  if (!test) throw Error(message);
}

function textValue_(value, limit, field) {
  check_(typeof value === 'string' && value.length <= limit
    && !/[\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/u.test(value),
  `Check ${field} for length or unsupported characters.`);
  return value.trim();
}

function listingUrl_(value, shared) {
  // Apps Script V8 lacks the browser URL API. Intake accepts a narrow HTTPS
  // subset with neither a userinfo component nor an encoded authority.
  check_(typeof value === 'string' && value.length <= 500
    && /^https:\/\/[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}(?:[/?#][^\s\\<>"`\u0000-\u001f\u007f]*)?$/i.test(value),
  'Enter an HTTPS listing URL.');
  return shared ? value.split(/[?#]/, 1)[0] : value;
}

function validateObservation_(input, { shared = false, now = new Date() } = {}) {
  check_(input && typeof input === 'object' && !Array.isArray(input), 'Expected an observation record.');
  const allowed = [
    'schemaVersion', 'id', 'observedAt', 'year', 'condition', 'priceCents',
    'type', 'scope', 'source', 'verification', 'mileage', 'zip', 'sellerType',
    'listingUrl', ...Object.keys(textLimits), ...(shared ? [] : ['interest', 'privateNotes']),
  ];
  check_(Object.keys(input).every(key => allowed.includes(key)), 'Unknown observation field.');
  const { schemaVersion, id, observedAt, year, condition, priceCents, type, scope, source, verification } = input;
  check_(schemaVersion === 1 && typeof id === 'string' && idPattern.test(id), 'Invalid observation identifier or version.');
  const date = typeof observedAt === 'string' ? new Date(observedAt) : new Date(NaN);
  check_(Number.isFinite(+date) && date.toISOString() === observedAt && +date >= Date.UTC(2020, 0, 1)
    && +date <= +now + 86400000, 'Invalid observation date.');
  check_(Number.isInteger(year) && year >= 1886 && year <= now.getUTCFullYear() + 2, 'Enter a valid model year.');
  check_(['new', 'used'].includes(condition), 'Select new or used.');
  check_((!shared && priceCents === null) || (Number.isInteger(priceCents) && priceCents > 0 && priceCents <= 1000000000),
    'Enter a positive USD price up to $10 million.');
  check_(Object.hasOwn(observationTypes, type) && Object.hasOwn(priceScopes, scope), 'Select a price type and scope.');
  check_(source === 'contributed' && verification === 'unverified', 'Invalid observation provenance.');
  const record = { schemaVersion, id, observedAt, year, condition, priceCents, type, scope, source, verification };
  for (const [field, limit] of Object.entries(textLimits)) {
    if (Object.hasOwn(input, field)) record[field] = textValue_(input[field], limit, field);
  }
  check_(record.make && record.model, 'Enter manufacturer and model.');
  if (record.catalogId !== undefined) {
    check_(/^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,99}$/.test(record.catalogId), 'Invalid catalog reference.');
  }
  if (Object.hasOwn(input, 'mileage')) {
    check_(Number.isInteger(input.mileage) && input.mileage >= 0 && input.mileage <= 2000000, 'Check vehicle mileage.');
    record.mileage = input.mileage;
  }
  if (Object.hasOwn(input, 'zip')) {
    check_(typeof input.zip === 'string' && /^[0-9]{5}$/.test(input.zip), 'Enter a five-digit ZIP code.');
    record.zip = input.zip;
  }
  if (Object.hasOwn(input, 'sellerType')) {
    check_(['dealer', 'private', 'other'].includes(input.sellerType), 'Select a seller type.');
    record.sellerType = input.sellerType;
  }
  if (Object.hasOwn(input, 'listingUrl')) record.listingUrl = listingUrl_(input.listingUrl, shared);
  if (!shared) {
    check_(interests.includes(input.interest), 'Invalid interest selection.');
    record.interest = input.interest;
    if (Object.hasOwn(input, 'privateNotes')) {
      check_(typeof input.privateNotes === 'string', 'Invalid private notes.');
      const notes = input.privateNotes.replace(/\r\n?/g, '\n');
      textValue_(notes.replace(/\n/g, ' '), 2000, 'private notes');
      record.privateNotes = notes;
    }
  }
  return record;
}

function sharedObservation_(record, includeDetails = false) {
  const { privateNotes, interest, listingUrl, nickname, vehicleNotes, zip, ...fields } = record;
  const optional = { listingUrl, nickname, vehicleNotes, zip };
  if (includeDetails) {
    for (const [key, value] of Object.entries(optional)) {
      if (value) fields[key] = value;
    }
  }
  return validateObservation_(fields, { shared: true });
}

function observationGroups_(records) {
  return interests.map(interest => [interest, records.filter(record => record.interest === interest)
    .sort((a, b) => (a.priceCents ?? Infinity) - (b.priceCents ?? Infinity)
      || a.observedAt.localeCompare(b.observedAt) || a.id.localeCompare(b.id))]);
}

function encodeObservations_(records, { markdown = false, shared = false } = {}) {
  const observations = records.map(record => shared
    ? validateObservation_(record, { shared: true }) : validateObservation_(record));
  const json = JSON.stringify({ format: 'csg-observations', version: 1, observations }, null, 2);
  return markdown ? `---\n${json}\n---\n` : json + '\n';
}

function decodeObservations_(contents, { shared = false } = {}) {
  check_(typeof contents === 'string' && contents.length <= 16000000, 'Observation file is too large.');
  const value = contents.trim().replace(/\r\n/g, '\n');
  const match = /^---\n([\s\S]+)\n---$/.exec(value);
  const parsed = JSON.parse(match?.[1] ?? value);
  check_(parsed?.format === 'csg-observations' && parsed.version === 1
    && Object.keys(parsed).every(key => ['format', 'version', 'observations'].includes(key))
    && Array.isArray(parsed.observations) && parsed.observations.length <= 10000,
  'Unsupported observation file.');
  const records = parsed.observations.map(record => validateObservation_(record, { shared }));
  check_(new Set(records.map(record => record.id)).size === records.length, 'Duplicate observation in file.');
  return records;
}
