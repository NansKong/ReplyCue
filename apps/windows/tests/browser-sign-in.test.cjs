const test = require('node:test');
const assert = require('node:assert/strict');
const { browserSignIn } = require('../electron/browser-sign-in.cjs');

test('browser handoff rejects a bad nonce and accepts the valid request only once', async () => {
  let opened;
  const ready = new Promise(resolve => { opened = resolve; });
  let calls = 0;
  const abort = new AbortController();
  const result = browserSignIn('github', async url => opened(new URL(url)), async tokens => {
    calls++;
    assert.deepEqual(tokens, { idToken: 'id-test', refreshToken: 'refresh-test' });
    return { configured: true };
  }, abort.signal);
  result.catch(() => {});
  try {
    const url = await ready;
    const fields = new URLSearchParams(url.hash.slice(1));
    assert.equal(url.origin, 'https://reply-cue.vercel.app');
    assert.equal(fields.get('provider'), 'github');
    const base = 'http://127.0.0.1:' + fields.get('port') + '/replycue/';
    const request = { method: 'POST', headers: { Origin: url.origin },
      body: new URLSearchParams({ idToken: 'id-test', refreshToken: 'refresh-test' }) };
    assert.equal((await fetch(base + 'wrong', request)).status, 403);
    assert.equal((await fetch(base + fields.get('nonce'), {
      ...request, headers: { Origin: 'https://invalid.example' },
    })).status, 403);
    assert.equal((await fetch(base + fields.get('nonce'), request)).status, 200);
    assert.deepEqual(await result, { configured: true });
    assert.equal(calls, 1);
  } finally {
    abort.abort();
  }
});
