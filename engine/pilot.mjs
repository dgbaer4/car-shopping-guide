import { energyCost, normalize } from './recommendation.mjs';
import { results } from './results.mjs';
import { indexPricing, priceConditions } from './vehicle-pricing.mjs';
import { pilotDefaults } from './pilot-cost.mjs';

export function recommendPilot(profile, catalog, { year, limit, pricing }) {
  const buyer = normalize(profile);
  const defaults = pilotDefaults(profile);
  const indexed = indexPricing(pricing);
  const priceByVehicle = new Map(catalog.vehicles.map(vehicle => {
    const records = indexed.get(vehicle.id) ?? {};
    const conditions = priceConditions(buyer, records);
    return [vehicle.id, { records, conditions }];
  }));
  const hasPrice = id => {
    const { records, conditions } = priceByVehicle.get(id);
    return records[conditions[0]] != null;
  };
  const vehicles = new Map(catalog.vehicles.map(vehicle => [vehicle.id, vehicle]));
  const compareEnergy = buyer.priorities.includes('Operating costs');
  const energy = new Map(catalog.vehicles.map(vehicle => [vehicle.id, energyCost({
    miles: defaults.annualMiles,
    mpg: vehicle.mpg,
    kwhPerMile: vehicle.kwhPerMile,
    electricShare: vehicle.power === 'Fully electric' ? 1 : vehicle.power === 'Plug-in hybrid' ? null : 0,
    gasPrice: defaults.gasPrice,
    electricPrice: defaults.electricPrice,
  })]));

  function orderCandidates(rows) {
    const group = new Map();
    for (const row of rows) {
      const vehicle = vehicles.get(row.id);
      const { records, conditions } = priceByVehicle.get(row.id);
      const family = records[conditions[0]]?.model ??
        vehicle.model.replace(/\s+(?:AWD|FWD|RWD|2WD|4WD|Blue|Eco)$/i, '');
      group.set(row.id, [vehicle.make, family].join(' '));
    }
    const selected = new Set();
    const prioritized = [];
    for (const status of ['eligible', 'conditional']) {
      const tier = rows.filter(row => row.status === status);
      tier.sort((a, b) => a.unknown.length - b.unknown.length ||
        Number(hasPrice(b.id)) - Number(hasPrice(a.id)) ||
        (compareEnergy ? (energy.get(a.id) ?? Infinity) - (energy.get(b.id) ?? Infinity) || 0 : 0) ||
        vehicles.get(b.id).year - vehicles.get(a.id).year || a.id.localeCompare(b.id));
      const unique = [], alternatives = [];
      for (const row of tier) {
        const family = group.get(row.id);
        if (selected.has(family)) alternatives.push(row);
        else {
          unique.push(row);
          selected.add(family);
        }
      }
      const kinds = new Set();
      const front = [];
      const first = unique[0];
      if (buyer.power.length > 1 && first) {
        for (const row of unique) {
          const power = vehicles.get(row.id).power;
          if (row.unknown.length !== first.unknown.length || !hasPrice(row.id) || kinds.has(power)) continue;
          front.push(row);
          kinds.add(power);
        }
      }
      const frontIds = new Set(front.map(row => row.id));
      prioritized.push(...front, ...unique.filter(row => !frontIds.has(row.id)), ...alternatives);
    }
    return prioritized;
  }

  const view = results(buyer, catalog.vehicles, year, { limit, orderCandidates });
  return {
    ...view,
    defaults,
    compareEnergy,
    budget: { ceiling: buyer.budget, flex: buyer.flex, allIn: buyer.allIn, exclusive: buyer.budgetExclusive },
    items: view.items.map(item => ({
      ...item,
      classification: item.explanation.status === 'eligible' ? 'Confirmed match' : 'Potential match',
      vehicle: vehicles.get(item.id),
      pricing: priceByVehicle.get(item.id),
    })),
  };
}
