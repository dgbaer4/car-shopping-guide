import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { recommend } from '../engine/integration.mjs';
import { evaluate, normalize } from '../engine/recommendation.mjs';

const read = path => JSON.parse(readFileSync(new URL('../data/' + path, import.meta.url), 'utf8'));
const catalog = read('vehicle-catalog-v0.3-integration.json');
const equipment = read('development/equipment/vehicle-equipment.v1.json');
const profile = { schemaVersion: '0.2', answers: { power: ['Gasoline'] }, features: {} };

test('pinned catalog produces deterministic eligible recommendations and paginates in fives', () => {
  const initial = recommend(profile, catalog, equipment, { year: 2026 });
  assert.equal(initial.items.length, 5);
  assert.ok(initial.excludedCount > 0);
  assert.ok(initial.items.every(item =>
    item.power === 'Gasoline' &&
    item.explanation.status === 'eligible' &&
    item.explanation.strengths.includes('Matches selected powertrain: Gasoline') &&
    item.ownership.cashOutlay.total === null &&
    item.ownership.netOwnership.total === null));
  const expanded = recommend(profile, catalog, equipment, { year: 2026, limit: initial.nextLimit });
  assert.equal(expanded.items.length, 10);
  assert.deepEqual(expanded.items.slice(0, 5), initial.items);
  assert.deepEqual(recommend(profile, { vehicles: [...catalog.vehicles].reverse() }, equipment, { year: 2026 }), initial);
});

test('unknown equipment stays unverified for both requirements and prohibitions', () => {
  for (const preference of ['Required', 'Prohibited', 'Desired']) {
    const requested = {
      ...profile,
      answers: { ...profile.answers, equipment: 'Yes, let’s explore' },
      features: { 'Heated front seats': preference },
    };
    const vehicle = catalog.vehicles.find(row => row.id === 'epa-48500');
    assert.equal(vehicle.features['Heated front seats'], null);
    const evaluation = evaluate(normalize(requested), vehicle, 2026);
    assert.equal(evaluation.equipmentScore, null);
    assert.deepEqual(evaluation.rejected, []);
    const view = recommend(requested, { vehicles: [vehicle] }, equipment, { year: 2026 });
    if (preference === 'Desired') {
      const item = view.items[0];
      assert.ok(item.explanation.verify.includes('Desired equipment unverified: Heated front seats'));
      assert.deepEqual(item.explanation.tradeoffs, []);
      assert.deepEqual(item.possibleTrims.map(trim => trim.facts[0].status), ['unavailable', 'package-dependent']);
    } else {
      assert.equal(view.conditionalCount, 1);
      assert.deepEqual(view.items, []);
    }
  }
});

test('safety evidence distinguishes unknown, unpublished, partial and review-required data', () => {
  const get = id => catalog.vehicles.find(row => row.id === 'epa-' + id);
  assert.equal(get(42428).safetyEvidence, 'unknown');
  assert.equal(get(42428).safetyRatings, null);
  assert.equal(get(47223).safetyEvidence, 'no-published-rating');
  assert.equal(get(47223).safetyRatings, null);
  assert.equal(get(44588).safetyEvidence, 'review-required');
  assert.deepEqual(get(44588).safetyRatings, { overall: null, frontal: 4, side: 5, rollover: null });
});

test('complete explicit cost inputs produce total, annual and monthly equivalents', () => {
  const vehicle = catalog.vehicles.find(row => row.id === 'epa-48500');
  const common = {
    years: 5, purchasePrice: 20000, taxesFees: 2000, annualMiles: 10000,
    gasPrice: 4, annualMaintenance: 500, annualInsurance: 1000, annualRegistration: 200, resaleValue: 10000,
  };
  const finance = { downPayment: 2000, apr: 0, loanMonths: 60 };
  const { items: [item] } = recommend(profile, { vehicles: [vehicle] }, equipment, {
    year: 2026, costsById: { [vehicle.id]: { ...common, ...finance } },
  });
  for (const view of [item.ownership.cashOutlay, item.ownership.netOwnership]) {
    assert.deepEqual(view.missing, []);
    assert.equal(view.total / common.years, view.annual);
    assert.equal(view.annual / 12, view.monthly);
  }
  assert.equal(item.ownership.cashOutlay.total - item.ownership.netOwnership.total, common.resaleValue);
  const incomplete = recommend(profile, { vehicles: [vehicle] }, equipment, {
    year: 2026, costsById: { [vehicle.id]: { ...common, ...finance, years: 2, resaleValue: null } },
  }).items[0].ownership;
  assert.ok(incomplete.cashOutlay.total > 0);
  assert.equal(incomplete.netOwnership.total, null);
  assert.deepEqual(incomplete.netOwnership.missing, ['resaleValue']);
  assert.ok(Math.abs(incomplete.remainingLoanBalance - 12000) < 1e-8);
});
