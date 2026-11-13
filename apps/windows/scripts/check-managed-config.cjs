const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {resolve} = require('node:path');
const config = JSON.parse(readFileSync(resolve(__dirname, '../../website/out/managed-config.json'), 'utf8').replace(/^\uFEFF/, ''));
assert.ok(typeof config.firebaseApiKey === 'string' && /^AIza[A-Za-z0-9_-]{35}$/.test(config.firebaseApiKey),
  'Missing desktop Firebase Auth configuration. Run Build.ps1 -ManagedRelease with the desktop configuration environment variables.');
assert.equal(config.gatewayUrl, 'https://replycue-gateway.vercel.app/api/ai',
  'Production gateway missing. Run Build.ps1 -ManagedRelease; do not package the website defaults directly.');
console.log('Managed installer configuration verified (Firebase Auth and production AI gateway).');
