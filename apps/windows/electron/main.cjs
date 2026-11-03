const { app, BrowserWindow, ipcMain, protocol, net, dialog, session, shell } = require('electron');
const { existsSync } = require('node:fs');
const { spawn } = require('node:child_process');
const { createInterface } = require('node:readline');
const { join, resolve, sep } = require('node:path');
const { pathToFileURL } = require('node:url');
protocol.registerSchemesAsPrivileged([{ scheme: 'copilot', privileges: { standard: true, secure: true, supportFetchAPI: true } }]);
let win, engine, serial = 0, quitting = false, latest;
const closeCheck = process.argv.includes('--check-close');
const checkMode = process.argv.includes('--check') || closeCheck;
if (checkMode) app.setPath('userData', join(app.getPath('temp'), 'copilot-startup-check'));
app.setAppUserModelId('local.teleprompter.copilot');
let preloadReady = false;
let browserLogin;
const assetFailures = [];
const pending = new Map();
const allowed = new Set(['state', 'sources', 'start', 'pause', 'end', 'overlay', 'configure', 'managed-sign-in', 'managed-sign-out']);
function currentWindow() {
  return win && !win.isDestroyed() ? win : null;
}
function request(action, data) {
  return new Promise((resolve, reject) => {
    if (!engine || engine.exitCode !== null || !engine.stdin.writable) return reject(new Error('The local engine is unavailable. Restart ReplyCue.'));
    const id = ++serial;
    const timeout = setTimeout(() => { pending.delete(id); reject(new Error('The engine did not respond. Please try again.')); }, 30000);
    pending.set(id, { resolve, reject, timeout });
    engine.stdin.write(JSON.stringify({ id, action, data }) + '\n');
  });
}
function validate(event) {
  const window = currentWindow();
  if (quitting || !window || window.webContents.isDestroyed() || event.sender !== window.webContents || event.senderFrame !== window.webContents.mainFrame || !event.senderFrame.url.startsWith('copilot://app/desktop/')) throw new Error('Untrusted sender.');
}
async function boot() {
  const root = resolve(__dirname, '../../..');
  const ui = app.isPackaged ? join(process.resourcesPath, 'ui') : join(root, 'apps/website/out');
  protocol.handle('copilot', async request => {
    const url = new URL(request.url);
    if (url.host !== 'app') return new Response('Not found', { status: 404 });
    let relative = decodeURIComponent(url.pathname);
    if (relative.endsWith('/')) relative += 'index.html';
    const target = resolve(ui, '.' + relative);
    if (!target.startsWith(resolve(ui) + sep)) return new Response('Not found', { status: 404 });
    let response;
    try { response = await net.fetch(pathToFileURL(target).toString()); }
    catch { assetFailures.push(relative); return new Response('Not found', { status: 404 }); }
    // Next static exports include inline hydration scripts; no remote code is allowed.
    response.headers.set('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self' https://identitytoolkit.googleapis.com; object-src 'none'; base-uri 'none'; frame-src 'none'");
    return response;
  });
  session.defaultSession.setPermissionRequestHandler((_web, _permission, callback) => callback(false));
  win = new BrowserWindow({ show: !checkMode, width: 1180, height: 820, minWidth: 880, minHeight: 660, backgroundColor: '#101513', title: 'ReplyCue', icon: join(__dirname, 'icon.ico'), autoHideMenuBar: true,
    webPreferences: { preload: join(__dirname, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true, spellcheck: false } });
  // Title-bar close destroys the native window before window-all-closed/quit.
  // Release the wrapper so delayed engine and app events cannot access it.
  win.on('closed', () => { win = null; });
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  win.webContents.on('will-navigate', (event, url) => { if (url !== 'copilot://app/desktop/') event.preventDefault(); });
  const currentConfig = join(app.getPath('userData'), '.env');
  const legacyConfig = ['Copilot', 'copilot-windows'].map(name => join(app.getPath('appData'), name, '.env'));
  const config = app.isPackaged
    ? (checkMode || existsSync(currentConfig) ? currentConfig : legacyConfig.find(path => existsSync(path)) || currentConfig)
    : join(root, '.env');
  const executable = app.isPackaged ? join(process.resourcesPath, 'engine/CopilotEngine.exe') : join(root, '.venv/Scripts/python.exe');
  const args = app.isPackaged ? ['--config', config] : [join(root, 'apps/windows/backend/bridge.py'), '--config', config];
  engine = spawn(executable, args, { windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'], env: { ...process.env, PYTHONIOENCODING: 'utf-8' } });
  engine.stdin.on('error', () => {});
  // No raw provider/backend output is persisted or forwarded to the renderer.
  engine.stderr.on('data', () => {});
  engine.on('error', () => { engine = null; if (!quitting) dialog.showErrorBox('ReplyCue engine', 'The local engine could not start. Reinstall ReplyCue or check the development runtime.'); });
  createInterface({ input: engine.stdout }).on('line', line => {
    let message; try { message = JSON.parse(line); } catch { return; }
    if (message.id && pending.has(message.id)) {
      const promise = pending.get(message.id); clearTimeout(promise.timeout); pending.delete(message.id);
      if (message.error) promise.reject(new Error(message.error)); else promise.resolve(message.result);
    }
    if (quitting || !currentWindow() || win.webContents.isDestroyed()) return;
    if (message.event === 'state') { latest = message.data; win.webContents.send('copilot:state', latest); }
    if (message.event === 'show' && !quitting) { win.show(); win.focus(); }
    if (message.event === 'hide' && !quitting) win.hide();
  });
  engine.on('exit', () => {
    for (const promise of pending.values()) { clearTimeout(promise.timeout); promise.reject(new Error('The engine stopped. Restart ReplyCue.')); }
    pending.clear();
    if (quitting) { engine = null; app.quit(); }
    else if (win && !win.isDestroyed()) { win.show(); win.webContents.send('copilot:state', { ...latest, live: false, busy: false, status: 'The local engine stopped. Restart ReplyCue.' }); }
  });
  ipcMain.handle('copilot:command', async (event, action, data) => {
    validate(event);
    if (action === 'browser-sign-in-cancel') {
      browserLogin?.abort();
      return;
    }
    if (action === 'browser-sign-in') {
      const state = await request('state');
      if (browserLogin || !state.managed || state.live || state.configured) {
        throw new Error('Browser sign-in is unavailable right now.');
      }
      const { browserSignIn } = require('./browser-sign-in.cjs');
      browserLogin = new AbortController();
      try {
        return await browserSignIn(data?.provider, url => shell.openExternal(url),
          tokens => request('managed-sign-in', tokens), browserLogin.signal);
      } finally {
        browserLogin = undefined;
      }
    }
    if (!allowed.has(action) || JSON.stringify(data ?? {}).length > 1100000) throw new Error('Invalid request.');
    return request(action, data);
  });
  ipcMain.on('copilot:ready', event => { if (quitting || !currentWindow()) return; validate(event); preloadReady = true; });
  ipcMain.handle('copilot:import', async event => {
    validate(event);
    const result = await dialog.showOpenDialog(win, { properties: ['openFile'], filters: [{ name: 'Documents', extensions: ['pdf', 'docx', 'txt'] }] });
    if (result.canceled) return null;
    return request('import', { path: result.filePaths[0] });
  });
  win.webContents.on('did-finish-load', () => { if (!quitting && latest && currentWindow() && !win.webContents.isDestroyed()) win.webContents.send('copilot:state', latest); });
  await win.loadURL('copilot://app/desktop/');
  if (quitting) return;
  if (checkMode) {
    const state = await request('state');
    const passed = preloadReady && assetFailures.length === 0 && Array.isArray(state.records);
    console.log(JSON.stringify({check:'desktop-startup',passed,preloadReady,assetFailures:assetFailures.length,engineConnected:Array.isArray(state.records)}));
    process.exitCode = passed ? 0 : 1;
    // Exercise the same native close path as the title-bar X, not only app.quit.
    if (closeCheck) win.close(); else app.quit();
  }
}
app.on('before-quit', event => {
  browserLogin?.abort();
  if (engine && engine.exitCode === null) {
    event.preventDefault();
    if (!quitting) { quitting = true; currentWindow()?.hide(); request('quit').catch(() => {}); }
  } else {
    quitting = true;
  }
});
app.on('window-all-closed', () => app.quit());
app.on('will-quit', () => {
  if (checkMode) console.log(JSON.stringify({ check: closeCheck ? 'window-close' : 'app-quit', passed: !currentWindow() && !engine }));
});
if (!checkMode && !app.requestSingleInstanceLock()) app.quit();
else { app.on('second-instance', () => { if (!quitting) { currentWindow()?.show(); currentWindow()?.focus(); } }); app.whenReady().then(boot).catch(error => { if (!quitting) dialog.showErrorBox('ReplyCue startup', error.message); app.quit(); }); }
