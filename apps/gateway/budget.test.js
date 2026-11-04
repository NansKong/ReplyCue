import test from 'node:test';
import assert from 'node:assert/strict';
import { hasUnlimitedUsage, reserve, reserveTrial } from './budget.js';

test('an exact cap can be reserved once and then rejects further requests', () => {
  const next = reserve(90, 10, 10, 100, 50);
  assert.deepEqual(next, { globalSpent: 100, userSpent: 20 });
  assert.equal(reserve(next.globalSpent, 0, 1, 100, 50), null);
});
test('trial cap applies independently of the global balance', () => {
  assert.equal(reserve(100, 45, 6, 1000, 50), null);
});
test('invalid ledger values cannot fail open', () => {
  assert.throws(() => reserve(-1, 0, 1, 100, 50));
  assert.throws(() => reserve(0, 0, 0, 100, 50));
});

test('an exhausted trial does not affect a second account', () => {
  assert.equal(reserveTrial(90_000, 10_000, 100_000), 100_000);
  assert.equal(reserveTrial(100_000, 1, 100_000), null);
  assert.equal(reserveTrial(0, 10_000, 100_000), 10_000);
});

test('unlimited access requires an exact verified UID in the server allowlist', () => {
  const identity = { uid: 'owner-123', email_verified: true };
  assert.equal(hasUnlimitedUsage(identity, ' teammate-456, owner-123 '), true);
  assert.equal(hasUnlimitedUsage(identity, ''), false);
  assert.equal(hasUnlimitedUsage(identity, 'owner-1234'), false);
  assert.equal(hasUnlimitedUsage(identity, '*'), false);
  assert.equal(hasUnlimitedUsage({ ...identity, email_verified: false }, 'owner-123'), false);
  assert.equal(hasUnlimitedUsage({ uid: 'other-user', email_verified: true, unlimited: true }, 'owner-123'), false);
});

test('an unlimited account keeps its usage ledger after passing the trial cap', () => {
  assert.equal(reserveTrial(100_000, 25_000, null), 125_000);
  assert.equal(reserveTrial(100_000, 25_000, 100_000), null);
  assert.equal(reserveTrial(0, 25_000, 100_000), 25_000);
  assert.throws(() => reserveTrial(0, 25_000, undefined));
  assert.throws(() => reserveTrial(Number.MAX_SAFE_INTEGER, 1, null));
});

test('an optional global cap still applies to unlimited accounts', () => {
  assert.deepEqual(reserve(25_000, 100_000, 25_000, 50_000, null), {
    globalSpent: 50_000, userSpent: 125_000,
  });
  assert.equal(reserve(50_000, 125_000, 25_000, 50_000, null), null);
});
