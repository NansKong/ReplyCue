const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const { resolve } = require('node:path');

const executable = resolve(__dirname, '../../..', 'releases/windows/win-unpacked/ReplyCue.exe');
async function check(flag, expected, extra = []) {
  const output = await new Promise((resolve, reject) => {
    const child = spawn(executable, [flag], { windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    let stdout = '', stderr = '';
    const timeout = setTimeout(() => {
      child.kill();
      reject(new Error(`Packaged ${expected} did not exit within 30 seconds`));
    }, 30000);
    child.stdout.on('data', data => { stdout += data; });
    child.stderr.on('data', data => { stderr += data; });
    child.on('error', error => { clearTimeout(timeout); reject(error); });
    child.on('close', code => {
      clearTimeout(timeout);
      if (code !== 0) reject(new Error(`Packaged ${expected} exited ${code}: ${stderr}`));
      else resolve(stdout);
    });
  });
  const checks = output.split(/\r?\n/).flatMap(line => {
    try { return [JSON.parse(line)]; } catch { return []; }
  });
  for (const name of ['desktop-startup', expected, ...extra]) {
    assert.ok(checks.some(check => check.check === name && check.passed), `Missing successful ${name}: ${output}`);
  }
  console.log(JSON.stringify({ check: expected, passed: true, exitCode: 0 }));
}
(async () => {
  await check('--check-close', 'window-close');
  await check('--check', 'app-quit');
  await check('--check-shortcuts', 'app-quit', ['overlay-shortcuts']);
})().catch(error => { console.error(error.message); process.exitCode = 1; });
