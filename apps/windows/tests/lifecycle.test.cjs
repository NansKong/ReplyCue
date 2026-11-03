const { test } = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');

// Run the real main process with strict window doubles: any access to a closed
// native window throws, just as Electron does when the title-bar X is clicked.
async function launch() {
  const app = new EventEmitter();
  const child = new EventEmitter();
  const lines = new EventEmitter();
  const writes = [], dialogs = [], timers = new Map();
  let window, quits = 0, timerId = 0;
  Object.assign(app, {
    isPackaged: false, getPath: () => 'C:/test',
    setAppUserModelId() {}, requestSingleInstanceLock: () => true,
    whenReady: () => Promise.resolve(),
    quit() {
      const event = { prevented: false, preventDefault() { this.prevented = true; } };
      app.emit('before-quit', event);
      if (!event.prevented) quits++;
    },
  });
  child.exitCode = null;
  child.stdin = new EventEmitter();
  child.stdin.writable = true;
  child.stdin.write = data => writes.push(JSON.parse(data));
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  class Window extends EventEmitter {
    constructor() {
      super(); window = this; this.destroyed = false; this.hidden = false;
      this.webContents = new EventEmitter();
      Object.assign(this.webContents, {
        mainFrame: {}, setWindowOpenHandler() {},
        isDestroyed: () => this.destroyed,
        send: () => this.check(),
      });
    }
    check() { if (this.destroyed) throw new TypeError('Object has been destroyed'); }
    isDestroyed() { return this.destroyed; }
    show() { this.check(); this.hidden = false; }
    focus() { this.check(); }
    hide() { this.check(); this.hidden = true; }
    loadURL() { return Promise.resolve(); }
    close() {
      this.destroyed = true;
      this.emit('closed');
      app.emit('window-all-closed');
    }
  }
  const electron = {
    app, BrowserWindow: Window,
    ipcMain: Object.assign(new EventEmitter(), { handle() {} }),
    protocol: { registerSchemesAsPrivileged() {}, handle() {} }, net: {},
    dialog: { showErrorBox: (...args) => dialogs.push(args) },
    session: { defaultSession: { setPermissionRequestHandler() {} } },
  };
  const main = join(__dirname, '../electron/main.cjs');
  vm.runInNewContext(readFileSync(main, 'utf8'), {
    require: id => id === 'electron' ? electron : id === 'node:child_process'
      ? { spawn: () => child } : id === 'node:readline'
        ? { createInterface: () => lines } : require(id),
    __dirname: join(__dirname, '../electron'),
    process: { argv: [], env: {} }, console, URL, Response,
    setTimeout: fn => { timers.set(++timerId, fn); return timerId; },
    clearTimeout: id => timers.delete(id),
  }, { filename: main });
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(dialogs, [], 'main process booted successfully');
  return { app, child, lines, window, writes, dialogs, timers, quits: () => quits,
    exit() { child.exitCode = 0; child.emit('exit', 0); } };
}

test('title-bar close waits for the engine without touching a destroyed window', async () => {
  const run = await launch();
  assert.doesNotThrow(() => run.window.close());
  assert.deepEqual(run.writes.map(m => m.action), ['quit']);
  assert.equal(run.quits(), 0, 'wait for native workers to finish');
  run.exit();
  assert.equal(run.quits(), 1);
  assert.equal(run.timers.size, 0);
});

test('repeated quit requests send one engine shutdown and hide the live window', async () => {
  const run = await launch();
  run.app.quit();
  run.app.quit();
  assert.equal(run.window.hidden, true);
  assert.deepEqual(run.writes.map(m => m.action), ['quit']);
  run.exit();
  assert.equal(run.quits(), 1);
});

test('second launches and late engine events do not reopen or access a closing window', async () => {
  const run = await launch();
  run.app.quit();
  run.app.emit('second-instance');
  assert.equal(run.window.hidden, true, 'shutdown must not reopen the workspace');
  run.window.close();
  assert.doesNotThrow(() => {
    run.app.emit('second-instance');
    run.lines.emit('line', JSON.stringify({ event: 'show' }));
    run.lines.emit('line', JSON.stringify({ event: 'state', data: {} }));
    run.window.webContents.emit('did-finish-load');
  });
  run.exit();
});

test('closing after the engine has stopped exits immediately', async () => {
  const run = await launch();
  run.exit();
  assert.doesNotThrow(() => run.window.close());
  assert.equal(run.quits(), 1);
  assert.equal(run.writes.length, 0);
});
