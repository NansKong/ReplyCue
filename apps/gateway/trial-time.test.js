import test from 'node:test';
import assert from 'node:assert/strict';
import { changeTrialSession, readTrial, trialUsage, TRIAL_LIMIT_MS } from './trial-time.js';

const now = 1_000_000;
const start = (account, id = 'session-a', at = now) =>
  ({ ...account, ...changeTrialSession(account, id, 'session-start', at).update });

test('older accounts begin with one hour, independent of their previous dollar ledger', () => {
  assert.equal(readTrial({ reserved: 100000 }, now).remainingMs, TRIAL_LIMIT_MS);
});

test('pause, idle, and resume count only active time across sessions', () => {
  let account = start({});
  account = { ...account, ...changeTrialSession(account, 'session-a', 'session-heartbeat', now + 10000).update };
  account = { ...account, ...changeTrialSession(account, 'session-a', 'session-stop', now + 15000).update };
  assert.equal(readTrial(account, now + 600000).usedMs, 15000);
  account = start(account, 'session-b', now + 600000);
  assert.equal(readTrial(account, now + 605000).usedMs, 20000);
});

test('a lost client consumes at most its 30-second lease and cannot renew an expired lease', () => {
  const account = start({});
  assert.equal(readTrial(account, now + 500000).usedMs, 30000);
  assert.equal(readTrial(account, now + 500000).running, false);
  assert.equal(changeTrialSession(account, 'session-a', 'session-heartbeat', now + 500000).code, 'session');
});

test('another device and a stale stop cannot replace the active session', () => {
  let account = start({});
  assert.equal(changeTrialSession(account, 'session-b', 'session-start', now + 1000).code, 'session_in_use');
  account = start(account, 'session-b', now + 40000);
  assert.equal(changeTrialSession(account, 'session-a', 'session-stop', now + 41000).code, 'session_in_use');
  assert.equal(readTrial(account, now + 41000).usedMs, 31000);
});

test('the final lease ends at exactly one hour and cannot be restarted', () => {
  const account = start({ trialUsedMs: TRIAL_LIMIT_MS - 1000 });
  assert.equal(account.trialLeaseUntilMs, now + 1000);
  assert.equal(readTrial(account, now + 1000).remainingMs, 0);
  assert.equal(changeTrialSession(account, 'session-a', 'session-start', now + 1000).code, 'trial');
  assert.equal(trialUsage(account, now + 1000, true).trialEnded, false);
  assert.equal(trialUsage(account, now + 1000, true).remainingTrialMs, null);
});

test('malformed persisted time cannot fail open', () => {
  assert.throws(() => readTrial({ trialUsedMs: -1 }, now));
  assert.throws(() => readTrial({ trialSessionId: 'a', trialTickAtMs: now, trialLeaseUntilMs: now + 60000 }, now));
});
