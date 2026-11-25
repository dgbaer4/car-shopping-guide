import { recommendPilot } from './pilot.mjs';
import { cashEstimate } from './pilot-cost.mjs';

let inputs;
async function readJson(path) {
  const response = await fetch(new URL(path, import.meta.url));
  if (!response.ok) throw Error('Catalog request failed');
  return response.json();
}

export async function loadResults(profile, limit) {
  inputs ??= Promise.all([
    readJson('../data/vehicle-catalog-v0.3-pilot.json'),
    readJson('../data/development/equipment/vehicle-equipment.v1.json'),
  ]).catch(error => {
    inputs = undefined;
    throw error;
  });
  const [catalog, equipment] = await inputs;
  const view = recommendPilot(profile, catalog, { year: new Date().getFullYear(), limit });
  const trims = new Map(equipment.trims.map(trim => [trim.id, trim]));
  const requested = Object.keys(profile.features);
  for (const item of view.items) {
    item.possibleTrims = item.vehicle.possibleTrimIds.map(id => {
      const trim = trims.get(id);
      return {
        name: trim.trim,
        facts: requested.map(name => {
          const fact = trim.facts[name];
          return { name, status: fact?.value ?? 'unknown', url: fact && equipment.sources[fact.source].url };
        }),
      };
    });
  }
  return view;
}

const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const money = value => value == null ? 'Unavailable' : currency.format(value);
const fields = [
  ['purchasePrice', 'Default vehicle price ($)'],
  ['salesTaxRate', 'Sales tax estimate (%)', 100],
  ['fees', 'One-time fees excluding annual registration ($)'],
  ['annualMiles', 'Miles per year'],
  ['years', 'Ownership period (years)', 40, 1, 1],
  ['gasPrice', 'Gas price ($/gal)'],
  ['electricPrice', 'Electricity price ($/kWh)'],
  ['phevElectricPercent', 'Plug-in hybrid electric miles (%)', 100],
  ['annualInsurance', 'Insurance per year ($)'],
  ['annualMaintenance', 'Maintenance per year ($)'],
  ['annualRegistration', 'Registration per year ($)'],
  ['resalePercent', 'Resale value at end of ownership (% of vehicle price)', 100],
];

function append(parent, tag, text = '') {
  const node = document.createElement(tag);
  node.textContent = text;
  parent.append(node);
  return node;
}

function numberInput(parent, [key, caption, max, min = 0, step = 'any'], value) {
  const label = append(parent, 'label', caption);
  const input = append(label, 'input');
  input.type = 'number';
  input.name = key;
  input.min = min;
  input.step = step;
  if (max != null) input.max = max;
  if (value != null) input.value = value;
  return input;
}

function budgetMessage(budget, cost) {
  const { ceiling, flex, allIn, exclusive } = budget;
  if (ceiling == null || allIn == null) return '';
  const amount = allIn ? cost.atPurchase : cost.purchasePrice;
  if (amount == null) return '';
  const measure = allIn ? 'cash at purchase' : 'vehicle price';
  const within = cap => exclusive ? amount < cap : amount <= cap;
  if (within(ceiling)) return `Estimated ${measure} is within your preferred budget. Verify the seller quote.`;
  if (flex && within(ceiling + flex)) return `Estimated ${measure} uses your stated budget flexibility. Verify the seller quote.`;
  return `Estimated ${measure} exceeds your preferred budget${flex ? ' plus flexibility' : ''}. Update it with a seller quote.`;
}

function renderEstimate(list, item, assumptions, quotePrice, budget) {
  const cost = cashEstimate(item.vehicle, assumptions, quotePrice);
  list.replaceChildren();
  const breakdown = [
    ['Vehicle price', cost.purchasePrice],
    ['Sales tax', cost.tax],
    ['One-time fees', cost.fees],
    ['Cash needed at purchase', cost.atPurchase],
    ['Energy per year', cost.annualEnergy],
    ['Total operating costs per year', cost.annualOperating],
    ['Estimated resale value', cost.resale],
  ];
  for (const [label, amount] of breakdown) {
    append(list, 'dt', label);
    append(list, 'dd', money(amount));
  }
  const years = assumptions.years;
  for (const [label, total] of [
    ['Cash expenditure', cost.cashExpenditure],
    ['Net ownership cost', cost.netOwnership],
  ]) {
    append(list, 'dt', label);
    append(list, 'dd', total == null ? 'Unavailable with the current inputs and EPA data.'
      : `${money(total)} over ${years} years · ${money(total / years)}/year · ${money(total / years / 12)} monthly equivalent`);
  }
  return budgetMessage(budget, cost);
}

export function renderResults(container, view, session) {
  session.assumptions ??= { ...view.defaults };
  container.replaceChildren();
  append(container, 'h1', 'Vehicle recommendations');
  const confirmed = view.totalCandidates - view.conditionalCount;
  append(container, 'p', `${confirmed} confirmed · ${view.conditionalCount} potential · ${view.excludedCount} excluded`);
  if (!view.items.length) {
    append(container, 'p', 'No configurations meet the selected constraints. Review your buyer profile to broaden your search.');
    return;
  }
  append(container, 'p', 'Confirmed matches satisfy the evaluated requirements. Potential matches still need listing or configuration details verified. Safety ratings are unavailable in the pilot.');
  if (view.compareEnergy) append(container, 'p', 'Within each match group, the shortlist prioritizes fewer items to verify and lower estimated energy costs using the starting assumptions. Editing costs updates the comparisons below.');
  append(container, 'p', 'Cash expenditure includes the purchase and running costs. Net ownership cost subtracts estimated resale value. Both cover the same ownership period.');
  const form = append(container, 'form');
  append(form, 'h2', 'Editable cash-purchase assumptions');
  append(form, 'p', 'Starting values are planning assumptions. The default price uses your budget when available and applies to every vehicle until you enter a vehicle-specific price. Replace tax, fees, running costs and resale assumptions with local figures or quotes.');
  const grid = append(form, 'div');
  grid.className = 'cost-grid';
  const inputs = fields.map(field => numberInput(grid, field, session.assumptions[field[0]]));
  const apply = append(form, 'button', 'Update cost estimates');
  apply.type = 'submit';
  const status = append(form, 'p');
  status.setAttribute('role', 'status');
  const cards = [];
  for (const item of view.items) {
    const card = append(container, 'article');
    append(card, 'h2', `${item.year} ${item.make} ${item.model}`);
    append(card, 'p', item.classification).className = 'match-status';
    const { mpg, kwhPerMile, drivetrain } = item.vehicle;
    append(card, 'p', [item.power, drivetrain, mpg != null ? `EPA ${mpg} MPG combined` : null,
      kwhPerMile != null ? `EPA ${kwhPerMile} kWh/mile` : null, item.id].filter(Boolean).join(' · '));

    for (const [label, entries] of [
      ['Verified strengths', item.explanation.strengths],
      ['Tradeoffs', item.explanation.tradeoffs],
      ['What to verify', item.explanation.verify.filter(text => !text.startsWith('Scoring evidence unavailable:'))],
    ]) {
      if (!entries.length) continue;
      append(card, 'h3', label);
      const list = append(card, 'ul');
      for (const entry of entries) append(list, 'li', entry);
    }

    if (item.possibleTrims.length) {
      const details = append(card, 'details');
      append(details, 'summary', 'Possible retail trims');
      append(details, 'p', 'Verify the exact trim and installed equipment with the seller.');
      for (const trim of item.possibleTrims) {
        append(details, 'h3', trim.name);
        for (const fact of trim.facts) {
          const row = append(details, 'p', `${fact.name} · ${fact.status}`);
          if (fact.url) append(row, 'a', ' Source').href = fact.url;
        }
      }
    }

    const estimate = append(card, 'div');
    estimate.className = 'estimate';
    const price = numberInput(estimate, ['vehiclePrice', 'Estimated vehicle price for this candidate ($)'], session.prices.get(item.id));
    price.placeholder = String(session.assumptions.purchasePrice ?? '');
    const list = append(estimate, 'dl');
    list.className = 'estimates';
    const budget = append(estimate, 'p');
    const update = () => {
      price.placeholder = String(session.assumptions.purchasePrice ?? '');
      budget.textContent = renderEstimate(list, item, session.assumptions, session.prices.get(item.id), view.budget);
    };
    price.addEventListener('change', () => {
      if (!price.reportValidity()) return;
      if (price.value === '') session.prices.delete(item.id);
      else session.prices.set(item.id, price.valueAsNumber);
      update();
    });
    cards.push(update);
    update();
  }

  form.addEventListener('submit', event => {
    event.preventDefault();
    session.assumptions = Object.fromEntries(inputs.map(input => [input.name, input.value === '' ? null : input.valueAsNumber]));
    for (const update of cards) update();
    status.textContent = 'Cost estimates updated.';
  });
}
