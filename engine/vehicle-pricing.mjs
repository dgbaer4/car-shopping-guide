export const priceDisclosure = 'Prices are representative US estimates by make, model, model year and new or used condition. They do not account for a specific vehicle’s mileage, ZIP code, trim or condition. Actual purchase prices may vary.';

export function indexPricing(snapshot) {
  const index = new Map();
  for (const { epaIds, ...record } of snapshot?.records ?? []) {
    for (const epaId of epaIds) {
      const conditions = index.get(epaId) ?? {};
      conditions[record.condition] = { ...record, attribution: snapshot.sources[record.source] };
      index.set(epaId, conditions);
    }
  }
  return index;
}

export function priceConditions(buyer, records) {
  if (buyer.condition === 'New only') return ['new'];
  if (buyer.condition === 'Used only') return ['used'];
  const preferred = buyer.condition === 'Prefer new' ? 'new' : 'used';
  const alternate = preferred === 'new' ? 'used' : 'new';
  if (buyer.condition == null || buyer.condition === 'No preference') {
    if (!records[preferred] && records[alternate]) return [alternate, preferred];
  }
  return [preferred, alternate];
}

export function assessBudget(budget, record, assumptions, input = {}) {
  const { ceiling, allIn, flex, exclusive } = budget;
  if (ceiling == null || allIn == null) return '';
  const measure = allIn ? 'out-the-door price' : 'vehicle price';
  const verified = allIn ? input.outTheDoor : input.confirmed ? input.price : null;
  const within = (value, limit) => exclusive ? value < limit : value <= limit;
  const compare = value => {
    if (within(value, ceiling)) return 'fits your preferred budget';
    if (flex != null && within(value, ceiling + flex)) return 'uses your stated budget flexibility';
    return flex == null ? 'exceeds your preferred budget' : 'exceeds your budget including stated flexibility';
  };
  if (verified != null) return `Confirmed quote: ${measure} ${compare(verified)}.`;
  const toBudget = amount => allIn
    ? assumptions.salesTaxRate == null || assumptions.fees == null ? null
      : amount * (1 + assumptions.salesTaxRate / 100) + assumptions.fees
    : amount;
  if (input.price != null) {
    const projected = toBudget(input.price);
    return projected == null ? 'Budget fit is unverified. Add tax and fees or a confirmed out-the-door quote.'
      : `Potential budget fit: estimated ${measure} ${compare(projected)}. Verify a seller quote.`;
  }
  if (!record || toBudget(record.low) == null) return 'Budget fit is unverified. Enter a seller quote for comparison.';
  const low = compare(toBudget(record.low)), high = compare(toBudget(record.high));
  const summary = low === high ? `the sourced range ${high}` : 'the range spans more than one budget bracket';
  return `Potential budget fit: ${summary}. Verify a seller quote.`;
}
