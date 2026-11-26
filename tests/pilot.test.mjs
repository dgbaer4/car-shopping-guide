import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { recommendPilot } from '../engine/pilot.mjs';
import { assessBudget } from '../engine/vehicle-pricing.mjs';
import { cashEstimate, pilotDefaults } from '../engine/pilot-cost.mjs';

const catalog = JSON.parse(readFileSync(new URL('../data/vehicle-catalog-v0.3-pilot.json', import.meta.url)));
const pricing = JSON.parse(readFileSync(new URL('../data/vehicle-pricing.v1.json', import.meta.url)));
const profile = {
  schemaVersion: '0.2',
  answers: {
    zip: 'Walnut Creek, CA', budget: '$22,000–$25,000', fees: 'Yes, everything',
    flex: 'Up to $2,000', commute: '10–25 miles', days: '5', annual: '10,000–15,000',
    keep: '3–5 years', power: ['Gasoline', 'Traditional hybrid', 'Fully electric'], home: 'Yes', work: 'Not available', body: ['Sedan', 'Hatchback'],
    people: '1–2 people', condition: 'Prefer used', age: 'Up to 5 years', mileage: 'Under 75,000',
    priorities: ['Operating costs', 'Reliability'], top: 'Operating costs', equipment: 'Yes, let’s explore',
  },
  features: { 'Adaptive cruise control': 'Required' },
};

test('Walnut Creek–Moraga commuter gets five potential matches and comparable cash estimates', () => {
  const initial = recommendPilot(profile, catalog, { year: 2026, pricing });
  assert.equal(initial.items.length, 5);
  assert.equal(initial.defaults.years, 4);
  assert.equal(initial.defaults.annualMiles, 12500);
  assert.ok(!Object.hasOwn(initial.defaults, 'purchasePrice'));
  assert.ok(initial.items.every(item =>
    item.classification === 'Potential match' &&
    item.explanation.verify.includes('Requirement unverified: Budget') &&
    item.explanation.verify.includes('Requirement unverified: Adaptive cruise control')));
  const withoutPrices = recommendPilot(profile, catalog, { year: 2026 });
  assert.deepEqual(initial.items.map(item => item.id), withoutPrices.items.map(item => item.id));
  assert.ok(initial.items.some(item => !item.pricing.records.used));
  assert.equal(initial.items[0].pricing.records.used.central, 24143);
  assert.equal(new Set(initial.items.map(item => item.power)).size, 3);
  const comparison = recommendPilot(profile, catalog, { year: 2026, pricing, pricedOnly: true });
  assert.equal(comparison.items.length, 5);
  const [electric, hybrid, gas] = comparison.items;
  assert.deepEqual([electric.power, hybrid.power, gas.power], ['Fully electric', 'Traditional hybrid', 'Gasoline']);
  const estimate = item => cashEstimate(item.vehicle, initial.defaults, item.pricing.records.used.central);
  const [evCost, hybridCost, gasCost] = [electric, hybrid, gas].map(estimate);
  assert.deepEqual([evCost.purchasePrice, hybridCost.purchasePrice, gasCost.purchasePrice], [24143, 27083, 16535]);
  assert.ok(evCost.annualEnergy < hybridCost.annualEnergy && hybridCost.annualEnergy < gasCost.annualEnergy);
  assert.ok(gasCost.netOwnership < evCost.netOwnership && evCost.netOwnership < hybridCost.netOwnership);
  assert.equal(gasCost.cashExpenditure - gasCost.netOwnership, gasCost.resale);
  const quoted = cashEstimate(hybrid.vehicle, initial.defaults, 21500);
  assert.equal(quoted.atPurchase, 24150);
  assert.equal(quoted.tax, 2150);
  assert.equal(quoted.fees, 500);
  assert.equal(quoted.annualOperating, hybridCost.annualOperating);
  assert.ok(quoted.netOwnership < hybridCost.netOwnership);
  assert.deepEqual(recommendPilot(profile, catalog, { year: 2026, limit: 10, pricing }).items.slice(0, 5), initial.items);
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
  const costs = cashEstimate(ev, defaults, 20000);
  assert.ok(costs.annualEnergy > 0);
  const missingResale = cashEstimate(ev, { ...defaults, resalePercent: null }, 20000);
  assert.equal(missingResale.cashExpenditure, costs.cashExpenditure);
  assert.equal(missingResale.netOwnership, null);
  assert.equal(cashEstimate(ev, { ...defaults, electricPrice: null }, 20000).cashExpenditure, null);
});

test('pilot data carries no unapproved ratings or NHTSA claim sources', () => {
  assert.equal(catalog.vehicles.length, 1253);
  for (const row of catalog.vehicles) {
    assert.ok(!Object.keys(row).some(key => /^safety/i.test(key)));
    assert.ok(row.sources.length && row.sources.every(source => source.url.startsWith('https://www.fueleconomy.gov/')));
  }
});

test('missing new and used price evidence never uses the shopper budget or another condition', () => {
  const id = pricing.records.find(row => row.condition === 'used' && row.model === 'Prius').epaIds[0];
  const vehicles = catalog.vehicles.filter(row => row.id === id);
  const newProfile = { ...profile, answers: { ...profile.answers, condition: 'New only' } };
  const { items: [item], defaults } = recommendPilot(newProfile, { vehicles }, { year: 2026, pricing });
  assert.deepEqual(item.pricing.conditions, ['new']);
  assert.equal(item.pricing.records.new, undefined);
  const cost = cashEstimate(item.vehicle, defaults);
  assert.equal(cost.purchasePrice, null);
  assert.equal(cost.cashExpenditure, null);
  assert.equal(cost.netOwnership, null);
  assert.ok(cost.annualOperating > 0);
});

test('a range or hypothetical price cannot confirm budget compatibility', () => {
  const assumptions = pilotDefaults(profile);
  const allIn = { ceiling: 25000, flex: 2000, allIn: true };
  const range = { low: 19000, high: 26000 };
  assert.match(assessBudget(allIn, range, assumptions), /spans.*Verify/);
  assert.match(assessBudget(allIn, range, assumptions, { price: 21500, confirmed: true }), /^Potential budget fit/);
  assert.match(assessBudget(allIn, range, assumptions, { outTheDoor: 24500 }), /^Confirmed quote:.*fits/);
  assert.match(assessBudget(allIn, null, assumptions, { outTheDoor: 28000 }), /exceeds your budget/);
  assert.match(assessBudget(allIn, null, assumptions), /unverified/);
  const vehicleOnly = { ceiling: 15000, flex: 0, allIn: false, exclusive: true };
  assert.match(assessBudget(vehicleOnly, null, assumptions, { price: 15000, confirmed: true }), /exceeds/);
  assert.match(assessBudget(vehicleOnly, null, assumptions, { price: 14999, confirmed: true }), /fits/);
});

test('condition-specific price evidence preserves distinct MSRP and used asking bases', () => {
  const vehicles = catalog.vehicles.filter(vehicle => vehicle.id === pricing.records.find(row =>
    row.model === 'K4' && row.condition === 'new').epaIds[0]);
  const { items: [item] } = recommendPilot({ ...profile, answers: {} }, { vehicles }, { year: 2026, pricing });
  assert.equal(item.pricing.records.new.priceBasis, 'msrp');
  assert.equal(item.pricing.records.used.priceBasis, 'asking');
  assert.notEqual(item.pricing.records.used.central, item.pricing.records.new.central);
  assert.equal(item.pricing.records.used.attribution.license, 'CC BY 4.0');
});

test('equally suitable models span available years regardless of source order or page size', () => {
  const vehicles = [2021, 2023, 2026].flatMap(year => ['Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon'].map(model => ({
    id: `${model}-${year}`, make: 'Test', model, year, power: 'Gasoline',
  })));
  const buyer = { ...profile, answers: {}, features: {} };
  const view = recommendPilot(buyer, { vehicles }, { year: 2026 });
  assert.equal(view.totalCandidates, vehicles.length);
  assert.equal(view.conditionalCount, 0);
  assert.equal(new Set(view.items.map(item => item.year)).size, 3);
  assert.equal(new Set(view.items.map(item => item.model)).size, 5);
  const reversed = recommendPilot(buyer, { vehicles: vehicles.toReversed() }, { year: 2026, limit: 10 });
  assert.deepEqual(view.items, reversed.items.slice(0, 5));
});

test('used age boundaries and new-only eligibility use condition evidence separately from model year', () => {
  const scoped = { vehicles: [
    { id: 'old-new', year: 2021, condition: 'new' },
    { id: 'used-five', year: 2021, condition: 'used' },
    { id: 'used-three', year: 2023, condition: 'used' },
    { id: 'current-unknown', year: 2026 },
  ].map(row => ({ make: 'Test', model: row.id, power: 'Gasoline', ...row })) };
  const get = answers => recommendPilot({ ...profile, answers, features: {} }, scoped, { year: 2026 });
  for (const [age, count] of [['Up to 3 years', 2], ['Up to 5 years', 3], ['No preference', 3]]) {
    const result = get({ condition: 'Used only', age });
    assert.equal(result.totalCandidates, count);
    assert.equal(result.conditionalCount, 1);
    assert.equal(result.items.at(-1).id, 'current-unknown');
  }
  const fresh = get({ condition: 'New only', age: 'Up to 3 years' });
  assert.deepEqual(fresh.items.map(item => item.id), ['old-new', 'current-unknown']);
  assert.equal(fresh.conditionalCount, 1);
  assert.deepEqual(get({ condition: 'Prefer used' }).items.map(item => item.id),
    ['used-five', 'used-three', 'current-unknown', 'old-new']);
});

test('year diversity stays below verification and energy cost in the order', () => {
  const vehicles = [
    { id: 'efficient', model: 'Alpha', year: 2026, mpg: 50, features: { 'Backup camera': true } },
    { id: 'less-efficient', model: 'Beta', year: 2026, mpg: 45, features: { 'Backup camera': true } },
    { id: 'older', model: 'Gamma', year: 2021, mpg: 40, features: { 'Backup camera': true } },
    { id: 'needs-verification', model: 'Delta', year: 2022, mpg: 55 },
  ].map(row => ({ make: 'Test', power: 'Gasoline', ...row }));
  const buyer = { ...profile, features: { 'Backup camera': 'Required' }, answers: {
    equipment: 'Yes, let’s explore', priorities: ['Operating costs'],
  } };
  const { items, conditionalCount } = recommendPilot(buyer, { vehicles }, { year: 2026 });
  assert.deepEqual(items.map(item => item.id), vehicles.map(vehicle => vehicle.id));
  assert.equal(conditionalCount, 1);
});

test('unrestricted budget ignores saved fee inclusion and flexibility while retaining prices and costs', () => {
  const buyer = { ...profile, answers: { ...profile.answers, budget: 'No budget restriction' } };
  const view = recommendPilot(buyer, catalog, { year: 2026, pricing });
  assert.deepEqual(view.budget, { mode: 'unrestricted', ceiling: null, flex: null, allIn: null, exclusive: false });
  assert.equal(view.conditionalCount, view.totalCandidates);
  assert.ok(view.items.every(item => !item.explanation.verify.includes('Requirement unverified: Budget')));
  assert.ok(view.items.some(item => item.pricing.records.used) && view.items.some(item => !item.pricing.records.used));
  const quote = cashEstimate(view.items[0].vehicle, view.defaults, 50000);
  assert.equal(quote.atPurchase, 55500);
  assert.ok(quote.annualOperating > quote.annualEnergy);
  assert.equal(assessBudget(view.budget, null, view.defaults, { outTheDoor: quote.atPurchase }), '');
  for (const [label, mode] of [["I'm not sure", 'unsure'], ['Unsure', 'unsure'], ['Over $30,000', 'range'], [profile.answers.budget, 'range']]) {
    const older = recommendPilot({ ...buyer, answers: { ...buyer.answers, budget: label } }, catalog, { year: 2026 });
    assert.equal(older.budget.mode, mode);
    assert.equal(older.budget.allIn, true);
    assert.equal(older.budget.flex, 2000);
    assert.equal(older.budget.ceiling, label === profile.answers.budget ? 25000 : null);
  }
});
