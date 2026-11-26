import assert from 'node:assert/strict';
import { createHash, createHmac } from 'node:crypto';
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

test('iPad setup validator is the deterministic Apps Script build', () => {
  assert.equal(readFileSync(new URL('../collection/ObservationValidation.gs', import.meta.url), 'utf8'), intakeValidator());
});

function intakeMock() {
  const code = intakeValidator() + '\n' + readFileSync(new URL('../collection/Intake.gs', import.meta.url), 'utf8');
  const rows = [['Observation_ID', 'Payload_SHA256']];
  const invite = 'fixture' + String(9101);
  const key = 'a'.repeat(64);
  let now = Date.now();
  const inviteState = value => JSON.stringify({
    digest: createHmac('sha256', key).update('invite:' + value).digest('hex'),
    expiresAt: new Date(now + 7 * 86400000).toISOString(),
  });
  const props = new Map([
    ['SPREADSHEET_ID', 'fixture'], ['INTAKE_OPEN', 'true'], ['TOKEN_KEY', key], ['INVITATION', inviteState(invite)],
  ]);
  let busy = false;
  let failFlush = false;
  let opened = 0;
  let uuid = 0;
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
    Date: class extends Date {
      constructor(...args) { super(...(args.length ? args : [now])); }
      static now() { return now; }
    },
    Utilities: {
      getUuid: () => 'cbc56e5e-0d64-4616-836e-' + String(++uuid).padStart(12, '0'),
      computeDigest: (_, text) => [...createHash('sha256').update(text).digest()],
      computeHmacSha256Signature: (text, secret) => [...createHmac('sha256', secret).update(text).digest()],
      DigestAlgorithm: { SHA_256: 1 }, Charset: { UTF_8: 1 },
    },
    PropertiesService: { getScriptProperties: () => ({
      getProperty: name => props.get(name), setProperty: (name, value) => props.set(name, value),
    }) },
    LockService: { getScriptLock: () => ({ tryLock: () => !busy, releaseLock() {} }) },
    SpreadsheetApp: {
      openById() { opened += 1; return { getSheetByName: () => sheet }; },
      flush() { if (failFlush) throw Error('mock write response lost'); },
    },
    HtmlService: {
      createTemplateFromFile: () => ({
        evaluate() { return { payload: this.payload, setTitle() { return this; }, addMetaTag() { return this; } }; },
      }),
    },
  });
  vm.runInContext(code, sandbox);
  return {
    sandbox, rows, props, invite, inviteState, opened: () => opened,
    busy(value) { busy = value; }, lostWrite(value) { failFlush = value; },
    advance(ms) { now += ms; },
    enroll: (value = invite, remember = true) => sandbox.enrollDevice(value, remember, 'b'.repeat(64)),
  };
}

test('Apps Script mock verifies enrollment, rotation, caps, suspension, expiry and revocation', () => {
  const { sandbox, rows, props, invite, inviteState, advance, enroll } = intakeMock();
  const hour = 3600000;
  const day = 24 * hour;
  const payload = fixture('shared');
  for (let block = 0; block < 3; block++) {
    for (let i = 0; i < 8; i++) assert.equal(enroll('wrong1234').status, 'rejected');
    assert.equal(enroll().status, 'limited');
    advance(hour);
  }
  assert.equal(enroll().status, 'limited');
  const rotated = invite + '0';
  props.set('INVITATION', inviteState(rotated));
  assert.equal(enroll().status, 'rejected');
  const remembered = enroll(rotated.toUpperCase());
  const session = enroll(rotated, false);
  assert.equal(remembered.status, 'enrolled');
  assert.match(remembered.token, /^[a-f0-9-]{36}\.[a-f0-9]{64}$/);
  assert.notEqual(remembered.token, session.token);
  assert.equal(props.get('DEVICE_' + remembered.id).includes(remembered.token), false);
  advance(13 * hour);
  assert.equal(sandbox.submitObservation(payload, session.token, true).status, 'unauthorized');
  props.set('INTAKE_OPEN', 'false');
  assert.equal(enroll(rotated).status, 'closed');
  assert.equal(sandbox.submitObservation(payload, remembered.token, true).status, 'closed');
  assert.equal(rows.length, 1);
  props.set('INTAKE_OPEN', 'true');
  assert.equal(sandbox.submitObservation(payload, remembered.token.slice(0, -1), true).status, 'unauthorized');
  for (let i = 0; i < 3; i++) {
    const reply = sandbox.submitObservation(payload, remembered.token, true);
    assert.ok(['received', 'duplicate'].includes(reply.status));
    assert.ok(reply.expiresAt > remembered.expiresAt);
    advance(29 * day);
  }
  assert.equal(sandbox.submitObservation(payload, remembered.token, true).status, 'duplicate');
  advance(3 * day);
  assert.equal(sandbox.submitObservation(payload, remembered.token, true).status, 'unauthorized');
  assert.equal(enroll(rotated).status, 'rejected');
  props.set('INVITATION', inviteState(rotated));
  const revoke = enroll(rotated);
  props.set('REVOKED_' + revoke.id, 'true');
  assert.equal(sandbox.submitObservation(payload, revoke.token, true).status, 'unauthorized');
});

test('Apps Script mock validates direct handoff, consent, limits and idempotent receipts', () => {
  const { sandbox, rows, props, opened, busy, lostWrite, enroll } = intakeMock();
  const token = enroll().token;
  const submit = (payload, consent = true) => sandbox.submitObservation(payload, token, consent);
  assert.equal(sandbox.doGet().payload, '');
  assert.equal(sandbox.doPost({ parameters: { payload: [fixture('private')] } }).payload, '');
  assert.equal(sandbox.doPost({ parameters: { payload: ['one', 'two'] } }).payload, '');
  const handoff = sandbox.doPost({ parameters: { payload: [fixture('shared')] } });
  assert.deepEqual(decodeObservations(handoff.payload, { shared: true }), [shared]);
  assert.equal(submit(fixture('shared'), false).status, 'rejected');
  assert.equal(submit(fixture('private')).status, 'rejected');
  assert.equal(submit('x'.repeat(8001)).status, 'rejected');
  assert.equal(submit('{broken').status, 'rejected');
  assert.equal(opened(), 0);
  const malicious = encodeObservations([{ ...shared, make: '=IMPORTXML("https://example.com")' }], { shared: true });
  busy(true);
  assert.equal(submit(malicious).status, 'retry');
  assert.equal(rows.length, 1);
  busy(false);
  lostWrite(true);
  assert.equal(submit(malicious).status, 'retry');
  lostWrite(false);
  const receipt = submit(malicious);
  assert.equal(receipt.status, 'duplicate');
  assert.equal(receipt.id, shared.id);
  assert.equal(receipt.receivedAt, rows[1][2]);
  assert.equal(rows.length, 2);
  assert.equal(rows[1][3], 'v2');
  assert.equal(rows[1][4][0], '{');
  assert.match(JSON.parse(rows[1][4]).make, /^=IMPORTXML/);
  assert.equal(submit(fixture('shared')).status, 'conflict');
  const other = encodeObservations([{ ...shared, id: otherId }], { shared: true });
  const today = new Date().toISOString().slice(0, 10);
  props.set('DAILY_WRITES', today + '/50');
  assert.equal(submit(other).status, 'limited');
  assert.equal(submit(malicious).status, 'duplicate');
  props.set('DAILY_WRITES', '2020-01-01/50');
  const deviceKey = 'DEVICE_' + token.split('.')[0];
  const device = JSON.parse(props.get(deviceKey));
  props.set(deviceKey, JSON.stringify({ ...device, day: today, writes: 10 }));
  assert.equal(submit(other).status, 'limited');
  props.set(deviceKey, JSON.stringify(device));
  assert.equal(submit(other).status, 'received');
  assert.equal(rows.length, 3);
  const updated = JSON.parse(props.get(deviceKey));
  props.set(deviceKey, JSON.stringify({ ...updated, attempts: 20 }));
  assert.equal(submit(other).status, 'limited');
});
