export const TRIAL_LIMIT_MS = 60 * 60 * 1000;
export const TRIAL_LEASE_MS = 30 * 1000;

export function readTrial(account, now) {
  const used = account.trialUsedMs ?? 0;
  if (!Number.isSafeInteger(used) || used < 0) throw new Error('Invalid trial time');
  const running = typeof account.trialSessionId === 'string' &&
    Number.isSafeInteger(account.trialTickAtMs) && Number.isSafeInteger(account.trialLeaseUntilMs);
  if (running && (account.trialTickAtMs < 0 ||
      account.trialLeaseUntilMs < account.trialTickAtMs ||
      account.trialLeaseUntilMs - account.trialTickAtMs > TRIAL_LEASE_MS)) {
    throw new Error('Invalid trial lease');
  }
  const elapsed = running ? Math.max(0, Math.min(now, account.trialLeaseUntilMs) - account.trialTickAtMs) : 0;
  const usedMs = Math.min(TRIAL_LIMIT_MS, used + elapsed);
  return { usedMs, remainingMs: TRIAL_LIMIT_MS - usedMs,
    running: running && account.trialLeaseUntilMs > now && usedMs < TRIAL_LIMIT_MS };
}

export function trialUsage(account, now, unlimited) {
  const trial = readTrial(account, now);
  return {
    unlimited, trialLimitMs: unlimited ? null : TRIAL_LIMIT_MS,
    remainingTrialMs: unlimited ? null : trial.remainingMs,
    trialEnded: !unlimited && trial.remainingMs === 0,
    trialRunning: !unlimited && trial.running, trialUpdatedAtMs: now,
    // Older Windows clients accept null balances for unlimited access.
    remainingMicroUsd: null, limitMicroUsd: null, minimumTurnMicroUsd: null,
  };
}

export function changeTrialSession(account, sessionId, action, now) {
  const trial = readTrial(account, now);
  if (action === 'session-stop') {
    if (trial.running && account.trialSessionId !== sessionId) return { code: 'session_in_use' };
    return { update: { trialUsedMs: trial.usedMs, trialSessionId: null,
      trialTickAtMs: null, trialLeaseUntilMs: null } };
  }
  if (trial.running && account.trialSessionId !== sessionId) return { code: 'session_in_use' };
  if (trial.remainingMs === 0) return { code: 'trial' };
  if (action === 'session-heartbeat' && (!trial.running || account.trialSessionId !== sessionId)) {
    return { code: 'session' };
  }
  return { update: { trialUsedMs: trial.usedMs, trialSessionId: sessionId,
    trialTickAtMs: now, trialLeaseUntilMs: now + Math.min(TRIAL_LEASE_MS, trial.remainingMs) } };
}
