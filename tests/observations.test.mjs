import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';
import { intakeValidator } from '../tools/build_observation_intake.mjs';
import {
  decodeObservations, encodeObservations, observationGroups, sharedObservation, validateObservation,
} from '../engine/observations.mjs';

const fixture = name => readFileSync(new URL(`fixtures/observations-${name}.json`, import.meta.url), 'utf8');
const [record] = decodeObservations(fixture('private'));
const [shared] = decodeObservations(fixture('shared'), { shared: true });
const otherId = '52a3fc63-287b-487a-9555-3742afbfdfa4';

test('portable single and collection exports preserve cents and private notes', () => {
  for (const markdown of [true, false]) {
    for (const observations of [[record], [record, { ...record, id: otherId, priceCents: null }]]) {
      assert.deepEqual(decodeObservations(encodeObservations(observations, { markdown })), observations);
    }
    assert.deepEqual(decodeObservations(encodeObservations([shared], { markdown, shared: true }), { shared: true }), [shared]);
  }
  assert.throws(() => decodeObservations(encodeObservations([record, record])), /Duplicate/);
});

test('shared exports require a price and omit private fields and URL tracking', () => {
  assert.deepEqual(sharedObservation(record, true), shared);
  assert.equal(shared.listingUrl, 'https://example.com/vehicles/123');
  for (const field of ['interest', 'privateNotes']) assert.equal(shared[field], undefined);
  for (const field of ['nickname', 'vehicleNotes', 'zip', 'listingUrl']) assert.equal(sharedObservation(record)[field], undefined);
  assert.throws(() => sharedObservation({ ...record, priceCents: null }), /positive USD/);
  assert.throws(() => decodeObservations(fixture('private'), { shared: true }), /Unknown observation field/);
});

test('validates all price types, conditions and scopes, and rejects malformed data', () => {
  for (const type of ['asking', 'quote', 'purchase']) {
    for (const condition of ['new', 'used']) {
      for (const scope of ['vehicle', 'out_the_door', 'unknown']) {
        assert.equal(validateObservation({ ...record, type, condition, scope }).type, type);
      }
    }
  }
  for (const fields of [
    { make: '' }, { model: undefined }, { year: '2023' }, { year: 33333 },
    { priceCents: 0 }, { priceCents: '123' }, { priceCents: 1.9 }, { priceCents: Infinity },
    { type: '__proto__' }, { scope: 'other' }, { condition: 'salvage' }, { mileage: -1 },
    { listingUrl: 'javascript:alert(1)' }, { listingUrl: 'https://bad.example@some.example/vehicle' },
    { listingUrl: 'https://example.com/\\oops' }, { nickname: '\u202einvalid' },
    { verification: 'verified' }, { observedAt: '2026-02-30T12:00:00.000Z' }, { email: 'a@example.org' },
  ]) assert.throws(() => validateObservation({ ...record, ...fields }));
});

test('tracker sorts missing prices last within each interest group', () => {
  const records = [
    { ...record, interest: 'POSSIBLE', priceCents: 100 },
    { ...record, priceCents: null },
    { ...record, priceCents: 400 },
    { ...record, priceCents: 200 },
    { ...record, interest: 'DON’T THINK SO', priceCents: 100 },
  ];
  assert.deepEqual(observationGroups(records).map(([group, list]) => [group, list.map(row => row.priceCents)]),
    [['GOOD', [200, 400, null]], ['POSSIBLE', [100]], ['DON’T THINK SO', [100]]]);
});

test('Apps Script mock enforces consent, invite, validation, limits and idempotent retry', () => {
  const code = intakeValidator() + '\n' + readFileSync(new URL('../collection/Intake.gs', import.meta.url), 'utf8');
  const rows = [['Observation_ID', 'Payload_SHA256']];
  const invite = 'f'.repeat(48);
  const props = new Map([['SPREADSHEET_ID', 'fixture'], ['INVITE_SHA256', createHash('sha256').update(invite).digest('hex')]]);
  let busy = false;
  let failFlush = false;
  let opened = 0;
  const sheet = {
    getLastRow: () => rows.length,
    appendRow: row => rows.push(row),
    getRange: (row, column) => ({
      getValue: () => rows[row - 1][column - 1],
      createTextFinder: id => ({
        matchEntireCell: () => ({
          findNext() {
            const index = rows.findIndex(item => item[0] === id);
            return index === -1 ? null : { getRow: () => index + 1 };
          },
        }),
      }),
    }),
  };
  const sandbox = vm.createContext({
    Utilities: {
      computeDigest: (_, text) => [...createHash('sha256').update(text).digest()],
      DigestAlgorithm: { SHA_256: 1 }, Charset: { UTF_8: 1 },
    },
    PropertiesService: { getScriptProperties: () => ({
      getProperty: key => props.get(key), setProperty: (key, value) => props.set(key, value),
    }) },
    LockService: { getScriptLock: () => ({ tryLock: () => !busy, releaseLock() {} }) },
    SpreadsheetApp: {
      openById() { opened += 1; return { getSheetByName: () => sheet }; },
      flush() { if (failFlush) throw Error('mock write response lost'); },
    },
  });
  vm.runInContext(code, sandbox);
  const submit = (payload, code = invite, consent = true) => sandbox.submitObservation(payload, code, consent).status;
  assert.equal(submit(fixture('shared'), invite, false), 'rejected');
  assert.equal(submit(fixture('shared'), 'e'.repeat(48)), 'rejected');
  assert.equal(submit(fixture('private')), 'rejected');
  assert.equal(submit('x'.repeat(8001)), 'rejected');
  assert.equal(submit('{broken'), 'rejected');
  assert.equal(opened, 0);
  const malicious = encodeObservations([{ ...shared, make: '=IMPORTXML("https://example.com")' }], { shared: true });
  busy = true;
  assert.equal(submit(malicious), 'retry');
  assert.equal(rows.length, 1);
  busy = false;
  failFlush = true;
  assert.equal(submit(malicious), 'retry');
  failFlush = false;
  assert.equal(submit(malicious), 'duplicate');
  assert.equal(rows.length, 2);
  assert.equal(rows[1][4][0], '{');
  assert.match(JSON.parse(rows[1][4]).make, /^=IMPORTXML/);
  assert.equal(submit(fixture('shared')), 'conflict');
  const other = encodeObservations([{ ...shared, id: otherId }], { shared: true });
  const today = new Date().toISOString().slice(0, 10);
  props.set('DAILY_WRITES', today + '/50');
  assert.equal(submit(other), 'retry');
  assert.equal(submit(malicious), 'duplicate');
  props.set('DAILY_WRITES', '2020-01-01/50');
  assert.equal(submit(other), 'received');
  assert.equal(rows.length, 3);
});
