import test from 'node:test';
import assert from 'node:assert/strict';
import { reserve } from './budget.js';

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
