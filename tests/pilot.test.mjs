import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { recommendPilot } from '../engine/pilot.mjs';
import { cashEstimate, pilotDefaults } from '../engine/pilot-cost.mjs';

const catalog = JSON.parse(readFileSync(new URL('../data/vehicle-catalog-v0.3-pilot.json', import.meta.url)));
const profile = {
  schemaVersion: '0.2',
  answers: {
    zip: 'Walnut Creek, CA', budget: '$22,000–$25,000', fees: 'Yes, everything',
    flex: 'Up to $2,000', commute: '10–25 miles', days: '5', annual: '10,000–15,000',
    keep: '3–5 years', power: ['Gasoline', 'Traditional hybrid'], body: ['Sedan', 'Hatchback'],
    people: '1–2 people', condition: 'Prefer used', age: 'Up to 5 years', mileage: 'Under 75,000',
    priorities: ['Operating costs', 'Reliability'], top: 'Operating costs', equipment: 'Yes, let’s explore',
  },
  features: { 'Adaptive cruise control': 'Required' },
};

test('Walnut Creek–Moraga commuter gets five potential matches and comparable cash estimates', () => {
  const initial = recommendPilot(profile, catalog, { year: 2026 });
  assert.equal(initial.items.length, 5);
  assert.equal(initial.defaults.years, 4);
  assert.equal(initial.defaults.annualMiles, 12500);
  assert.equal(initial.items[0].model, 'Ioniq Blue');
  assert.equal(initial.items[1].model, 'Prius');
  assert.ok(initial.items.every(item =>
    item.classification === 'Potential match' &&
    item.explanation.verify.includes('Requirement unverified: Budget') &&
    item.explanation.verify.includes('Requirement unverified: Adaptive cruise control')));
  const a = cashEstimate(initial.items[0].vehicle, initial.defaults);
  const b = cashEstimate(initial.items[1].vehicle, initial.defaults);
  assert.equal(a.atPurchase, 26350);
  assert.equal(a.cashExpenditure - a.netOwnership, 10575);
  assert.ok(a.annualEnergy < b.annualEnergy);
  assert.ok(a.netOwnership < b.netOwnership);
  const quoted = cashEstimate(initial.items[1].vehicle, initial.defaults, 21500);
  assert.equal(quoted.atPurchase, 24150);
  assert.ok(quoted.netOwnership < a.netOwnership);
  assert.deepEqual(recommendPilot(profile, catalog, { year: 2026, limit: 10 }).items.slice(0, 5), initial.items);
});

test('confirmed hard constraints precede potential ones and exclusions stay out', () => {
  const vehicle = catalog.vehicles.find(row => row.power === 'Gasoline');
  const scoped = { vehicles: [
    { ...vehicle, id: 'a', features: { 'Backup camera': null } },
    { ...vehicle, id: 'b', features: { 'Backup camera': true } },
    { ...vehicle, id: 'c', features: { 'Backup camera': false } },
  ] };
  const camera = { ...profile, answers: { equipment: 'Yes, let’s explore' }, features: { 'Backup camera': 'Required' } };
  const view = recommendPilot(camera, scoped, { year: 2026 });
  assert.deepEqual(view.items.map(item => [item.id, item.classification]), [['b', 'Confirmed match'], ['a', 'Potential match']]);
  assert.equal(view.excludedCount, 1);
});

test('changing resale leaves cash expenditure intact and missing energy never becomes free', () => {
  const defaults = pilotDefaults(profile);
  const ev = catalog.vehicles.find(row => row.power === 'Fully electric');
  const costs = cashEstimate(ev, defaults);
  assert.ok(costs.annualEnergy > 0);
  const missingResale = cashEstimate(ev, { ...defaults, resalePercent: null });
  assert.equal(missingResale.cashExpenditure, costs.cashExpenditure);
  assert.equal(missingResale.netOwnership, null);
  assert.equal(cashEstimate(ev, { ...defaults, electricPrice: null }).cashExpenditure, null);
});

test('pilot data carries no unapproved ratings or NHTSA claim sources', () => {
  assert.equal(catalog.vehicles.length, 1406);
  for (const row of catalog.vehicles) {
    assert.ok(!Object.keys(row).some(key => /^safety/i.test(key)));
    assert.ok(row.sources.length && row.sources.every(source => source.url.startsWith('https://www.fueleconomy.gov/')));
  }
});
