const { contextBridge, ipcRenderer } = require('electron');
ipcRenderer.send('copilot:ready');
contextBridge.exposeInMainWorld('copilot', {
  command: (action, data) => ipcRenderer.invoke('copilot:command', action, data),
  importDocument: () => ipcRenderer.invoke('copilot:import'),
  onState: (callback) => {
    const listener = (_event, state) => callback(state);
    ipcRenderer.on('copilot:state', listener);
    return () => ipcRenderer.removeListener('copilot:state', listener);
  }
});
