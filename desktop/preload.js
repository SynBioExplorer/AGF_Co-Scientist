/**
 * AGF Co-Scientist — Electron preload script.
 *
 * Exposes a controlled, sandbox-safe API to the renderer process via
 * contextBridge. The renderer (React app) reaches Electron via
 * `window.electronAPI`.
 */

'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  getBackendUrl: () => ipcRenderer.invoke('backend:getUrl'),
  openFolder: () => ipcRenderer.invoke('dialog:openFolder'),
  openMailto: (url) => ipcRenderer.invoke('shell:openMailto', url),
  openExternal: (url) => ipcRenderer.invoke('shell:openExternal', url),
  showInFolder: (path) => ipcRenderer.invoke('shell:showItemInFolder', path),
  checkForUpdates: () => ipcRenderer.invoke('app:checkForUpdates'),
  onUpdateAvailable: (cb) => ipcRenderer.on('update:available', cb),
  onUpdateDownloaded: (cb) => ipcRenderer.on('update:downloaded', cb),
});
