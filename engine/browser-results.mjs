import { recommend } from './integration.mjs';

let inputs;
async function readJson(path) {
  const response = await fetch(new URL(path, import.meta.url));
  if (!response.ok) throw Error('Catalog request failed');
  return response.json();
}

export async function loadResults(profile, limit) {
  inputs ??= Promise.all([
    readJson('../data/vehicle-catalog-v0.3-integration.json'),
    readJson('../data/development/equipment/vehicle-equipment.v1.json'),
  ]).catch(error => {
    inputs = undefined;
    throw error;
  });
  const [catalog, equipment] = await inputs;
  return recommend(profile, catalog, equipment, { year: new Date().getFullYear(), limit });
}

const number = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const labels = {
  purchasePrice: 'purchase price', taxesFees: 'taxes and fees', downPayment: 'down payment',
  apr: 'APR', loanMonths: 'loan term', annualMaintenance: 'maintenance', annualInsurance: 'insurance',
  annualRegistration: 'registration', resaleValue: 'resale value', years: 'ownership period',
  energy: 'annual mileage, fuel or electricity prices, and applicable energy use',
  mpg: 'combined MPG', kwhPerMile: 'kWh per mile', electricShare: 'share of miles on electricity',
};

export function renderResults(container, view) {
  function append(parent, tag, text) {
    const child = document.createElement(tag);
    child.textContent = text;
    parent.append(child);
    return child;
  }

  container.replaceChildren();
  append(container, 'h1', 'Vehicle recommendations');
  if (!view.items.length) append(container, 'p', 'No configuration meets all requirements with the available evidence.');
  if (view.items.length) append(container, 'p', 'Monthly equivalents spread ownership costs over the ownership period. Loan payments are calculated separately.');
  append(container, 'p', `${view.totalCandidates} eligible · ${view.conditionalCount} need verification · ${view.excludedCount} excluded`);
  for (const item of view.items) {
    const card = append(container, 'article', '');
    append(card, 'h2', `${item.year} ${item.make} ${item.model}`);
    append(card, 'p', `${item.classification} · ${item.power} · ${item.trim} (${item.id})`);
    const explanation = item.explanation;
    append(card, 'p', explanation.headline);
    for (const [label, entries] of [
      ['Verified strengths', explanation.strengths],
      ['Tradeoffs', explanation.tradeoffs],
      ['What to verify', explanation.verify],
    ]) {
      if (!entries.length) continue;
      append(card, 'h3', label);
      const list = append(card, 'ul', '');
      for (const entry of entries) append(list, 'li', entry);
    }

    const safetyMessage = {
      'review-required': 'Safety rating applicability awaits independent approval.',
      'no-published-rating': 'The linked NHTSA variant has no published stars. Applicability awaits independent approval.',
      unknown: 'Safety rating applicability is unknown.',
    };
    append(card, 'p', safetyMessage[item.safetyEvidence]);

    if (item.possibleTrims.length) {
      const details = append(card, 'details', '');
      append(details, 'summary', 'Possible retail trims');
      append(details, 'p', 'Verify the exact trim and equipment for the vehicle you are considering.');
      for (const trim of item.possibleTrims) {
        append(details, 'h3', trim.name);
        for (const fact of trim.facts) {
          const row = append(details, 'p', `${fact.name} · ${fact.status}`);
          if (fact.source) {
            const link = append(row, 'a', ' Source');
            link.href = fact.source;
          }
        }
      }
    }

    const perspectives = [
      ['Cash outlay', item.ownership.cashOutlay, 'Payments made during the ownership period, including running costs.'],
      ['Net ownership cost', item.ownership.netOwnership, 'Depreciation, taxes and fees, interest paid, and running costs.'],
    ];
    for (const [label, cost, description] of perspectives) {
      append(card, 'h3', label);
      append(card, 'p', description);
      if (cost.total == null) {
        append(card, 'p', 'Total, annual and monthly-equivalent costs are unknown.');
        append(card, 'p', 'Inputs needed include ' + cost.missing.map(field => labels[field] ?? field).join(', ') + '.');
      } else {
        append(card, 'p', `${number.format(cost.total)} over ${cost.assumptions.years} years · ${number.format(cost.annual)} per year · ${number.format(cost.monthly)} monthly equivalent`);
      }
      const assumptions = Object.entries(cost.assumptions)
        .filter(([, value]) => value != null)
        .map(([field, value]) => `${labels[field] ?? field} = ${value}`);
      if (assumptions.length) append(card, 'p', 'Assumptions include ' + assumptions.join(', ') + '.');
    }
    if (item.ownership.remainingLoanBalance > 0) {
      append(card, 'p', `Estimated loan balance at the end of the period is ${number.format(item.ownership.remainingLoanBalance)}.`);
    }
  }
}
