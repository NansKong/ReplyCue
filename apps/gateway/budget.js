export function reserve(globalSpent, userSpent, cost, globalLimit, userLimit) {
  if (![globalSpent, userSpent, cost, globalLimit, userLimit].every(
    value => Number.isSafeInteger(value) && value >= 0
  ) || cost === 0) throw new Error('Invalid budget configuration');
  if (cost > globalLimit - globalSpent || cost > userLimit - userSpent) return null;
  return { globalSpent: globalSpent + cost, userSpent: userSpent + cost };
}
