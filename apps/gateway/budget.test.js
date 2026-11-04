import test from 'node:test';
import assert from 'node:assert/strict';
import { reserve, reserveTrial } from './budget.js';

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
