import { energyCost, normalize } from './recommendation.mjs';
import { results } from './results.mjs';
import { indexPricing, priceConditions } from './vehicle-pricing.mjs';
import { pilotDefaults } from './pilot-cost.mjs';

export function recommendPilot(profile, catalog, { year, limit, pricing, pricedOnly = false }) {
  const buyer = normalize(profile);
  const defaults = pilotDefaults(profile);
  const indexed = indexPricing(pricing);
  const priceByVehicle = new Map(catalog.vehicles.map(vehicle => {
    const records = indexed.get(vehicle.id) ?? {};
    const conditions = priceConditions(buyer, records);
    return [vehicle.id, { records, conditions }];
  }));
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

  const preferredCondition = { 'Prefer new': 'new', 'Prefer used': 'used' }[buyer.condition];
  const families = new Map(catalog.vehicles.map(({ id, make, model }) => {
    // EPA model labels mix family, drivetrain, trim, and battery variants.
    const namedFamily = model.match(/^(?:Accord|Altima|ARIYA|bZ Woodland|bZ4X|bZ|Civic|EV6|EV9|Ioniq [569]|LEAF|Prius|Sentra)(?=\s|$)/i)?.[0];
    const family = namedFamily ??
      model.replace(/\s+(?:AWD|FWD|RWD|2WD|4WD|HEV|PHEV|Hybrid|Plug-in Hybrid|Electric|Blue|Eco)(?:\s.*)?$/i, '');
    return [id, `${make} ${family.toLowerCase()}`];
  }));
  const fitsBody = vehicle => Number(buyer.body.includes(vehicle.body));
  const conditionFit = vehicle => {
    if (!preferredCondition || vehicle.condition == null) return 0;
    return vehicle.condition === preferredCondition ? 1 : -1;
  };
  const compareFit = (a, b) =>
    a.unknown.length - b.unknown.length ||
    conditionFit(vehicles.get(b.id)) - conditionFit(vehicles.get(a.id)) ||
    fitsBody(vehicles.get(b.id)) - fitsBody(vehicles.get(a.id)) ||
    b.matched.length - a.matched.length ||
    a.missing.length - b.missing.length;
  const compareCost = (a, b) => compareEnergy
    ? (energy.get(a.id) ?? Infinity) - (energy.get(b.id) ?? Infinity) || 0
    : 0;
  const compareSuitability = (a, b) => compareFit(a, b) || compareCost(a, b);

  function orderCandidates(rows) {
    const prioritized = [];
    const usedFamilies = new Set();
    for (const status of ['eligible', 'conditional']) {
      const ranked = rows.filter(row => row.status === status).sort((a, b) =>
        compareSuitability(a, b) || a.id.localeCompare(b.id));
      const yearsShown = new Map();
      const yearCount = row => yearsShown.get(vehicles.get(row.id).year) ?? 0;
      const take = row => {
        const modelYear = vehicles.get(row.id).year;
        yearsShown.set(modelYear, yearCount(row) + 1);
        usedFamilies.add(families.get(row.id));
        prioritized.push(row);
      };

      // Prefer distinct families within each fit level. Efficiency orders that
      // level when requested. Year variety resolves ties at the same cost.
      for (let start = 0; start < ranked.length;) {
        let end = start + 1;
        while (end < ranked.length && !compareFit(ranked[start], ranked[end])) end++;
        const remaining = ranked.slice(start, end);
        const representedPower = new Set();
        const takeBest = predicate => {
          let best = -1;
          for (let i = 0; i < remaining.length; i++) {
            const row = remaining[i];
            if (best >= 0 && compareCost(row, remaining[best]) > 0) break;
            if (predicate(row) && (best < 0 || yearCount(row) < yearCount(remaining[best]))) best = i;
          }
          if (best < 0) return false;
          const [row] = remaining.splice(best, 1);
          take(row);
          representedPower.add(vehicles.get(row.id).power);
          return true;
        };
        const freshFamily = row => !usedFamilies.has(families.get(row.id));
        if (buyer.power.length > 1) {
          while (representedPower.size < buyer.power.length && takeBest(row =>
            freshFamily(row) && !representedPower.has(vehicles.get(row.id).power))) { /* One per selected powertrain. */ }
        }
        while (takeBest(freshFamily)) { /* One per family before alternatives. */ }
        while (takeBest(() => true)) { /* Include remaining configurations for pagination. */ }
        start = end;
      }
    }
    return prioritized;
  }

  const candidates = pricedOnly ? catalog.vehicles.filter(vehicle => {
    const { records, conditions } = priceByVehicle.get(vehicle.id);
    return records[conditions[0]] != null;
  }) : catalog.vehicles;
  const view = results(buyer, candidates, year, { limit, orderCandidates });
  return {
    ...view,
    defaults,
    compareEnergy,
    budget: { mode: buyer.budgetMode, ceiling: buyer.budget, flex: buyer.flex, allIn: buyer.allIn, exclusive: buyer.budgetExclusive },
    items: view.items.map(item => ({
      ...item,
      classification: item.explanation.status === 'eligible' ? 'Confirmed match' : 'Potential match',
      vehicle: vehicles.get(item.id),
      pricing: priceByVehicle.get(item.id),
    })),
  };
}
