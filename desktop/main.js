/**
 * AGF Co-Scientist — Electron main process
 *
 * Responsibilities:
 *   1. Spawn the Python sidecar (FastAPI uvicorn) on app startup.
 *   2. Wait for the sidecar to write its port to `<userData>/port.txt`.
 *   3. Create a BrowserWindow that loads the React frontend.
 *      - Production: `frontend/dist/index.html`
 *      - Development: `http://localhost:5173`
 *   4. Bridge IPC handlers for shell/dialog operations.
 *   5. Hook up `electron-updater` for GitHub Releases auto-update.
 *   6. Enforce single-instance lock; handle macOS dock activation.
 */

'use strict';

const path = require('path');
const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');

const SidecarManager = require('./sidecar');
const { initUpdater, checkForUpdatesManual } = require('./updater');

const isDev =
  process.env.NODE_ENV === 'development' || !app.isPackaged;

let mainWindow = null;
let sidecar = null;

// ---------------------------------------------------------------------------
// Single-instance lock
// ---------------------------------------------------------------------------
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
  process.exit(0);
}

app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

// ---------------------------------------------------------------------------
// Window creation
// ---------------------------------------------------------------------------
async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    title: 'AGF Co-Scientist',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  if (isDev) {
    await mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    const indexPath = path.join(
      __dirname,
      '..',
      'frontend',
      'dist',
      'index.html'
    );
    await mainWindow.loadFile(indexPath);
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// ---------------------------------------------------------------------------
// IPC handlers
// ---------------------------------------------------------------------------
function registerIpcHandlers() {
  ipcMain.handle('dialog:openFolder', async () => {
    const result = await dialog.showOpenDialog({
      properties: ['openDirectory'],
    });
    if (result.canceled || result.filePaths.length === 0) {
      return null;
    }
    return result.filePaths[0];
  });

  ipcMain.handle('shell:openMailto', async (_event, url) => {
    if (typeof url !== 'string' || !url.startsWith('mailto:')) {
      throw new Error('shell:openMailto requires a mailto: URL');
    }
    await shell.openExternal(url);
    return true;
  });

  ipcMain.handle('shell:openExternal', async (_event, url) => {
    if (typeof url !== 'string') {
      throw new Error('shell:openExternal requires a URL string');
    }
    await shell.openExternal(url);
    return true;
  });

  ipcMain.handle('shell:showItemInFolder', async (_event, itemPath) => {
    if (typeof itemPath !== 'string') {
      throw new Error('shell:showItemInFolder requires a path string');
    }
    shell.showItemInFolder(itemPath);
    return true;
  });

  ipcMain.handle('backend:getUrl', () => {
    if (!sidecar) return null;
    return sidecar.getUrl();
  });

  ipcMain.handle('app:checkForUpdates', async () => {
    return checkForUpdatesManual();
  });
}

// ---------------------------------------------------------------------------
// App lifecycle
// ---------------------------------------------------------------------------
app.whenReady().then(async () => {
  registerIpcHandlers();

  sidecar = new SidecarManager({
    userDataDir: app.getPath('userData'),
    isDev,
  });

  try {
    await sidecar.start();
    console.log(`[main] Sidecar ready at ${sidecar.getUrl()}`);
  } catch (err) {
    console.error('[main] Failed to start sidecar:', err);
    dialog.showErrorBox(
      'Backend failed to start',
      `The AGF Co-Scientist backend could not start.\n\n${err.message}`
    );
    app.quit();
    return;
  }

  await createWindow();

  // electron-updater (no-op in dev)
  if (!isDev) {
    initUpdater(mainWindow);
  }

  app.on('activate', async () => {
    // macOS: re-create window when dock icon is clicked
    if (BrowserWindow.getAllWindows().length === 0) {
      await createWindow();
    }
  });
});

// ---------------------------------------------------------------------------
// Shutdown — graceful sidecar termination
// ---------------------------------------------------------------------------
let isQuitting = false;

app.on('before-quit', async (event) => {
  if (isQuitting) return;
  isQuitting = true;
  event.preventDefault();

  if (sidecar) {
    try {
      await sidecar.stop({ timeoutMs: 5000 });
    } catch (err) {
      console.error('[main] Sidecar stop error:', err);
    }
  }

  app.exit(0);
});

app.on('window-all-closed', () => {
  // On macOS keep the app alive; on other platforms quit so the sidecar dies.
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Export for test harnesses
module.exports = { isDev };
