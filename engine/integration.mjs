import { normalize } from './recommendation.mjs';
import { results } from './results.mjs';
import { ownershipCost } from './ownership-cost.mjs';

function costView(cost, input) {
  return {
    total: cost.total,
    annual: cost.annual ?? null,
    monthly: cost.annual == null ? null : cost.annual / 12,
    missing: cost.missing,
    assumptions: input,
  };
}

export function recommend(profile, catalog, equipment, { year, limit, costsById = {} }) {
  const buyer = normalize(profile);
  const trims = new Map(equipment.trims.map(trim => [trim.id, trim]));
  const vehicles = new Map(catalog.vehicles.map(vehicle => [vehicle.id, vehicle]));
  const requestedFeatures = [...new Set([...buyer.required, ...buyer.desired, ...buyer.prohibited])];
  const view = results(buyer, catalog.vehicles, year, { limit, eligibleOnly: true });

  return {
    ...view,
    items: view.items.map(({ ownership, ...item }) => {
      const vehicle = vehicles.get(item.id);
      const assumptions = {
        purchasePrice: vehicle.price ?? null,
        mpg: vehicle.mpg ?? null,
        kwhPerMile: vehicle.kwhPerMile ?? null,
        electricShare: vehicle.power === 'Fully electric' ? 1 : vehicle.power === 'Plug-in hybrid' ? null : 0,
        ...costsById[item.id],
      };
      if (buyer.payment === 'Cash') {
        assumptions.apr = 0;
        assumptions.loanMonths = 0;
        assumptions.downPayment = Number.isFinite(assumptions.purchasePrice) && Number.isFinite(assumptions.taxesFees)
          ? assumptions.purchasePrice + assumptions.taxesFees : null;
      }
      const cost = ownershipCost(assumptions);
      const { resaleValue, ...cashAssumptions } = assumptions;

      return {
        ...item,
        safetyEvidence: vehicle.safetyEvidence,
        possibleTrims: (vehicle.possibleTrimIds ?? []).map(id => {
          const trim = trims.get(id);
          if (!trim) throw Error('Missing equipment trim ' + id);
          return {
            name: trim.trim,
            facts: requestedFeatures.map(name => {
              const fact = trim.facts[name];
              return {
                name,
                status: fact?.value ?? 'unknown',
                source: fact ? equipment.sources[fact.source].url : null,
              };
            }),
          };
        }),
        ownership: {
          cashOutlay: costView(cost.cashOutlay, cashAssumptions),
          netOwnership: costView(cost, assumptions),
          remainingLoanBalance: cost.remainingLoanBalance ?? null,
        },
      };
    }),
  };
}
