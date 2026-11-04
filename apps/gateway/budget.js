export function hasUnlimitedUsage(identity, allowedUids = process.env.UNLIMITED_USER_UIDS) {
  return identity.email_verified === true && typeof identity.uid === 'string' &&
    Boolean(allowedUids?.split(',').map(value => value.trim()).filter(Boolean).includes(identity.uid));
}

export function reserveTrial(userSpent, cost, userLimit) {
  if (![userSpent, cost].every(value => Number.isSafeInteger(value) && value >= 0) ||
      (userLimit !== null && (!Number.isSafeInteger(userLimit) || userLimit < 0)) ||
      cost === 0 || !Number.isSafeInteger(userSpent + cost)) throw new Error('Invalid trial budget');
  return userLimit !== null && cost > userLimit - userSpent ? null : userSpent + cost;
}

export function reserve(globalSpent, userSpent, cost, globalLimit, userLimit) {
  if (![globalSpent, globalLimit].every(
    value => Number.isSafeInteger(value) && value >= 0
  )) throw new Error('Invalid budget configuration');
  const nextUserSpent = reserveTrial(userSpent, cost, userLimit);
  if (cost > globalLimit - globalSpent || nextUserSpent === null) return null;
  return { globalSpent: globalSpent + cost, userSpent: nextUserSpent };
}
