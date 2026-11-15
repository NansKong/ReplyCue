const test = require('node:test');
const assert = require('node:assert/strict');
const { browserSignIn } = require('../electron/browser-sign-in.cjs');

test('project connection posts only its GitHub credential and rejects replay during verification', async () => {
  let opened, release;
  const ready = new Promise(resolve => { opened = resolve; });
  const verified = new Promise(resolve => { release = resolve; });
  const abort = new AbortController();
  let calls = 0;
  const token = 'gho_' + 'x'.repeat(36);
  const result = browserSignIn('github', async url => opened(new URL(url)), async credentials => {
    calls++;
    assert.deepEqual(credentials, { githubToken: token });
    await verified;
    return { githubConnected: true };
  }, abort.signal, 'projects');
  result.catch(() => {});
  try {
    const url = await ready;
    const values = new URLSearchParams(url.hash.slice(1));
    assert.equal(values.get('purpose'), 'projects');
    assert.ok(!url.href.includes(token));
    const callback = 'http://127.0.0.1:' + values.get('port') + '/replycue/' + values.get('nonce');
    const request = body => ({ method:'POST', headers:{ Origin:url.origin }, body:new URLSearchParams(body) });
    assert.equal((await fetch(callback, request({idToken:'wrong-type',refreshToken:'wrong-type'}))).status,400);
    assert.equal((await fetch(callback, request({githubToken:'x'.repeat(513)}))).status,400);
    const accepted = fetch(callback,request({githubToken:token}));
    while (!calls) await new Promise(resolve=>setTimeout(resolve,5));
    assert.equal((await fetch(callback,request({githubToken:token}))).status,403);
    release();
    assert.equal((await accepted).status,200);
    assert.deepEqual(await result,{githubConnected:true});
    assert.equal(calls,1);
  } finally { release(); abort.abort(); }
});

test('project handoff cannot be requested with a non-GitHub provider', async () => {
  await assert.rejects(browserSignIn('google',async()=>{},async()=>{},new AbortController().signal,'projects'),/Unsupported connection/);
});
