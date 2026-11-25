import { recommendPilot } from './pilot.mjs';
import { cashEstimate } from './pilot-cost.mjs';
import { assessBudget, priceDisclosure } from './vehicle-pricing.mjs';

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
    readJson('../data/vehicle-pricing.v1.json'),
  ]).catch(error => {
    inputs = undefined;
    throw error;
  });
  const [catalog, equipment, pricing] = await inputs;
  const view = recommendPilot(profile, catalog, { year: new Date().getFullYear(), limit, pricing });
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

function renderEstimate(list, item, assumptions, purchasePrice) {
  const cost = cashEstimate(item.vehicle, assumptions, purchasePrice);
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
}

export function renderResults(container, view, session) {
  session.conditions ??= new Map();
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
  if (view.compareEnergy) append(container, 'p', 'Within each match group, the shortlist prioritizes fewer items to verify, available price evidence and lower estimated energy costs using the starting assumptions. Editing costs updates the comparisons below.');
  append(container, 'p', 'Cash expenditure includes the purchase and running costs. Net ownership cost subtracts estimated resale value. Both cover the same ownership period.');
  append(container, 'p', priceDisclosure);
  const form = append(container, 'form');
  append(form, 'h2', 'Editable cash-purchase assumptions');
  append(form, 'p', 'Tax, fees, running costs and resale start with editable planning assumptions. Each vehicle uses its sourced central price when available. Enter a vehicle-specific price to compare a quote or an alternative scenario.');
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
    const conditionLabel = append(estimate, 'label', 'Purchase condition');
    const condition = append(conditionLabel, 'select');
    condition.setAttribute('aria-label', 'Purchase condition');
    for (const value of item.pricing.conditions) {
      const option = append(condition, 'option', value === 'new' ? 'New' : 'Used');
      option.value = value;
    }
    condition.value = session.conditions.get(item.id) ?? item.pricing.conditions[0];
    const evidence = append(estimate, 'p');
    const price = numberInput(estimate, ['vehiclePrice', 'Vehicle purchase price override ($)']);
    const quoteLabel = append(estimate, 'label', 'Vehicle price is confirmed by the seller ');
    const confirmed = append(quoteLabel, 'input');
    confirmed.type = 'checkbox';
    const allIn = view.budget.allIn
      ? numberInput(estimate, ['outTheDoor', 'Confirmed out-the-door seller quote ($), for budget comparison'])
      : null;
    const list = append(estimate, 'dl');
    list.className = 'estimates';
    const budget = append(estimate, 'p');
    budget.setAttribute('aria-live', 'polite');
    const key = () => `${item.id}/${condition.value}`;
    const update = () => {
      const input = session.prices.get(key()) ?? {};
      const record = item.pricing.records[condition.value];
      price.value = input.price ?? '';
      price.placeholder = record?.central ?? '';
      confirmed.checked = input.confirmed ?? false;
      if (allIn) allIn.value = input.outTheDoor ?? '';
      evidence.replaceChildren();
      if (record) {
        const basis = {
          asking: 'Advertised asking prices, observed low–high and mean',
          msrp: 'Manufacturer MSRP reference, low–high and median across published grades',
          transaction: 'Reported transaction prices, low–high and median',
        };
        evidence.append(`${basis[record.priceBasis]}: ${money(record.low)}–${money(record.high)} · central ${money(record.central)} · ${record.referenceDate}. `);
        const sample = record.priceBasis === 'msrp' ? 'grades' : 'observations';
        if (record.sampleSize != null) evidence.append(`${record.sampleSize} ${sample}. `);
        if (record.confidence === 'limited') evidence.append('Limited listing sample. ');
        evidence.append(record.priceBasis === 'msrp'
          ? 'MSRP excludes destination. Add it to one-time fees if applicable. '
          : 'Observed extremes can differ from typical asking prices. ');
        const source = append(evidence, 'a', record.attribution.name);
        source.href = record.attribution.url;
        if (record.attribution.licenseUrl) {
          evidence.append(' · ');
          append(evidence, 'a', record.attribution.license).href = record.attribution.licenseUrl;
        }
      } else {
        evidence.textContent = 'Sourced pricing is unavailable for this model year and condition. Enter a price to estimate acquisition and ownership costs.';
      }
      renderEstimate(list, item, session.assumptions, input.price ?? record?.central ?? null);
      budget.textContent = assessBudget(view.budget, record, session.assumptions, input);
    };
    condition.addEventListener('change', () => {
      session.conditions.set(item.id, condition.value);
      update();
    });
    price.addEventListener('change', () => {
      if (!price.reportValidity()) return;
      const input = session.prices.get(key()) ?? {};
      session.prices.set(key(), { ...input, price: price.value === '' ? null : price.valueAsNumber, confirmed: false });
      update();
    });
    confirmed.addEventListener('change', () => {
      const input = session.prices.get(key()) ?? {};
      session.prices.set(key(), { ...input, confirmed: confirmed.checked && input.price != null });
      update();
    });
    allIn?.addEventListener('change', () => {
      if (!allIn.reportValidity()) return;
      const input = session.prices.get(key()) ?? {};
      session.prices.set(key(), { ...input, outTheDoor: allIn.value === '' ? null : allIn.valueAsNumber });
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
