/**
 * Auto-update wrapper around `electron-updater`.
 *
 *   - On launch (`initUpdater`) checks for updates immediately, then
 *     re-checks every 6 hours.
 *   - Sends IPC events `update:available` and `update:downloaded` to the
 *     renderer process so the UI can prompt the user.
 *   - `checkForUpdatesManual()` exposes a manual trigger via IPC.
 *
 * Note: electron-updater pulls `latest{,-mac}.yml` from the GitHub Release
 * configured in `build/electron-builder.yml` (`publish.provider: github`).
 */

'use strict';

const SIX_HOURS_MS = 6 * 60 * 60 * 1000;

let autoUpdater = null;
let intervalHandle = null;
let mainWindowRef = null;

function _lazyLoadUpdater() {
  if (autoUpdater) return autoUpdater;
  try {
    // Lazy-require so unit tests can run without electron-updater installed.
    // eslint-disable-next-line global-require
    autoUpdater = require('electron-updater').autoUpdater;
  } catch (err) {
    console.warn(
      '[updater] electron-updater not available — auto-update disabled.',
      err.message
    );
    autoUpdater = null;
  }
  return autoUpdater;
}

/**
 * Wire up auto-update on application startup.
 * @param {import('electron').BrowserWindow} mainWindow
 */
function initUpdater(mainWindow) {
  mainWindowRef = mainWindow;
  const updater = _lazyLoadUpdater();
  if (!updater) return;

  updater.autoDownload = true;
  updater.autoInstallOnAppQuit = true;

  updater.on('update-available', (info) => {
    console.log('[updater] update-available', info && info.version);
    if (mainWindowRef && !mainWindowRef.isDestroyed()) {
      mainWindowRef.webContents.send('update:available', info);
    }
  });

  updater.on('update-downloaded', (info) => {
    console.log('[updater] update-downloaded', info && info.version);
    if (mainWindowRef && !mainWindowRef.isDestroyed()) {
      mainWindowRef.webContents.send('update:downloaded', info);
    }
  });

  updater.on('error', (err) => {
    console.error('[updater] error:', err && err.message);
  });

  // Fire-and-forget. Failures are logged but non-fatal.
  updater.checkForUpdatesAndNotify().catch((err) => {
    console.error('[updater] initial check failed:', err && err.message);
  });

  if (intervalHandle) clearInterval(intervalHandle);
  intervalHandle = setInterval(() => {
    updater.checkForUpdatesAndNotify().catch((err) => {
      console.error('[updater] periodic check failed:', err && err.message);
    });
  }, SIX_HOURS_MS);
}

/**
 * Manual update check invoked via IPC (`app:checkForUpdates`).
 */
async function checkForUpdatesManual() {
  const updater = _lazyLoadUpdater();
  if (!updater) {
    return { ok: false, reason: 'updater-unavailable' };
  }
  try {
    const result = await updater.checkForUpdates();
    return { ok: true, updateInfo: result ? result.updateInfo : null };
  } catch (err) {
    return { ok: false, reason: err && err.message };
  }
}

module.exports = { initUpdater, checkForUpdatesManual };
