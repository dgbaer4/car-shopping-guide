import { energyCost, normalize } from './recommendation.mjs';
import { ownershipCost } from './ownership-cost.mjs';

function midpoint(range, fallback) {
  return range && range[1] != null ? (range[0] + range[1]) / 2 : range?.[0] || fallback;
}

export function pilotDefaults(profile) {
  const buyer = normalize(profile);
  return {
    salesTaxRate: 10,
    fees: 500,
    annualMiles: Math.round(midpoint(buyer.annualMiles, 10000)),
    years: Math.max(1, Math.round(midpoint(buyer.ownershipYears, 5))),
    gasPrice: 4.50,
    electricPrice: 0.30,
    phevElectricPercent: 50,
    annualInsurance: 1500,
    annualMaintenance: 700,
    annualRegistration: 250,
    resalePercent: 45,
  };
}

export function cashEstimate(vehicle, assumptions, purchasePrice = null) {
  const tax = purchasePrice == null || assumptions.salesTaxRate == null
    ? null : purchasePrice * assumptions.salesTaxRate / 100;
  const resale = purchasePrice == null || assumptions.resalePercent == null
    ? null : purchasePrice * assumptions.resalePercent / 100;
  const atPurchase = tax == null || assumptions.fees == null ? null : purchasePrice + tax + assumptions.fees;
  const electricShare = vehicle.power === 'Fully electric' ? 1
    : vehicle.power === 'Plug-in hybrid' ? assumptions.phevElectricPercent == null ? null : assumptions.phevElectricPercent / 100
    : 0;
  const cost = ownershipCost({
    ...assumptions,
    purchasePrice, taxesFees: atPurchase == null ? null : tax + assumptions.fees,
    downPayment: atPurchase, apr: 0, loanMonths: 0, resaleValue: resale,
    electricShare, mpg: vehicle.mpg, kwhPerMile: vehicle.kwhPerMile,
  });
  const annualEnergy = energyCost({ miles: assumptions.annualMiles, mpg: vehicle.mpg,
    kwhPerMile: vehicle.kwhPerMile, electricShare, gasPrice: assumptions.gasPrice, electricPrice: assumptions.electricPrice });
  const annualOperating = [annualEnergy, assumptions.annualInsurance, assumptions.annualMaintenance, assumptions.annualRegistration].some(value => value == null) ? null
    : annualEnergy + assumptions.annualInsurance + assumptions.annualMaintenance + assumptions.annualRegistration;
  return { purchasePrice, tax, fees: assumptions.fees, atPurchase, resale, annualEnergy, annualOperating,
    cashExpenditure: cost.cashOutlay.total, netOwnership: cost.total };
}
