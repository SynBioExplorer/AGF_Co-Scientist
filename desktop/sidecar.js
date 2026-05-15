/**
 * SidecarManager — spawns and supervises the Python FastAPI backend.
 *
 * Production:
 *   - Spawns the PyInstaller-bundled binary at
 *     `process.resourcesPath/sidecar/agf-coscientist-backend{ext}`.
 *   - Passes `AGF_DATA_DIR=<userData>` so the sidecar knows where to write
 *     its port file.
 *   - Watches `<userData>/port.txt` for up to `PORT_WAIT_MS` ms.
 *
 * Development:
 *   - Spawns `python -m uvicorn src.api.main:app --host 127.0.0.1 --port 0`
 *     from the repo root.
 *   - Falls back to reading the port from stdout via regex if the
 *     port file is missing (the Python team may not yet have wired the
 *     file-write hook).
 *
 * Lifecycle:
 *   - `start()` resolves once the URL is known.
 *   - `stop({ timeoutMs })` sends SIGTERM, force-kills with SIGKILL
 *     after the timeout (default 5 s).
 */

'use strict';

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const PORT_WAIT_MS = 15000;
const PORT_POLL_INTERVAL_MS = 200;

class SidecarManager {
  /**
   * @param {object} opts
   * @param {string} opts.userDataDir - Where the sidecar writes port.txt.
   * @param {boolean} opts.isDev - If true, run via `python -m uvicorn`.
   */
  constructor(opts = {}) {
    this.userDataDir = opts.userDataDir || process.cwd();
    this.isDev = Boolean(opts.isDev);
    this.proc = null;
    this.port = null;
    this.portFile = path.join(this.userDataDir, 'port.txt');
  }

  getUrl() {
    if (!this.port) return null;
    return `http://127.0.0.1:${this.port}`;
  }

  /**
   * Spawn the sidecar and resolve once the port is known.
   * @returns {Promise<string>} resolves with the backend URL.
   */
  async start() {
    // Clear any stale port file before launch so we don't pick up a
    // port from a previous run.
    try {
      if (fs.existsSync(this.portFile)) {
        fs.unlinkSync(this.portFile);
      }
    } catch (_) {
      /* ignore */
    }

    if (this.isDev) {
      this._spawnDev();
    } else {
      this._spawnProd();
    }

    this.port = await this._waitForPort();
    return this.getUrl();
  }

  /**
   * Spawn the bundled PyInstaller executable.
   * @private
   */
  _spawnProd() {
    const ext = process.platform === 'win32' ? '.exe' : '';
    const binary = path.join(
      process.resourcesPath,
      'sidecar',
      `agf-coscientist-backend${ext}`
    );

    this.proc = spawn(binary, [], {
      cwd: path.dirname(binary),
      env: {
        ...process.env,
        AGF_DATA_DIR: this.userDataDir,
        AGF_BIND_HOST: '127.0.0.1',
        AGF_BIND_PORT: '0',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    this._wireProcessLogging();
  }

  /**
   * Spawn `python -m uvicorn` from the repo root for development.
   * @private
   */
  _spawnDev() {
    const repoRoot = path.resolve(__dirname, '..');
    const pythonBin = process.env.AGF_PYTHON || 'python';
    this.proc = spawn(
      pythonBin,
      [
        '-m',
        'uvicorn',
        'src.api.main:app',
        '--host',
        '127.0.0.1',
        '--port',
        '0',
      ],
      {
        cwd: repoRoot,
        env: {
          ...process.env,
          AGF_DATA_DIR: this.userDataDir,
          PYTHONUNBUFFERED: '1',
        },
        stdio: ['ignore', 'pipe', 'pipe'],
      }
    );

    this._wireProcessLogging();
  }

  _wireProcessLogging() {
    if (!this.proc) return;

    // Try to harvest the port from uvicorn's stdout as a dev fallback.
    const portRegex =
      /Uvicorn running on https?:\/\/127\.0\.0\.1:(\d+)/i;

    const onData = (buf) => {
      const text = buf.toString();
      process.stdout.write(`[sidecar] ${text}`);
      if (!this.port) {
        const match = text.match(portRegex);
        if (match) {
          this.port = parseInt(match[1], 10);
        }
      }
    };

    this.proc.stdout.on('data', onData);
    this.proc.stderr.on('data', onData);

    this.proc.on('exit', (code, signal) => {
      console.log(
        `[sidecar] process exited code=${code} signal=${signal}`
      );
    });

    this.proc.on('error', (err) => {
      console.error('[sidecar] spawn error:', err);
    });
  }

  /**
   * Poll for the port file (or the stdout-harvested port) until found
   * or the timeout elapses.
   * @returns {Promise<number>}
   * @private
   */
  _waitForPort() {
    const deadline = Date.now() + PORT_WAIT_MS;

    return new Promise((resolve, reject) => {
      const tick = () => {
        // Did stdout already give us a port?
        if (this.port) {
          resolve(this.port);
          return;
        }

        // Try the port file.
        try {
          if (fs.existsSync(this.portFile)) {
            const raw = fs.readFileSync(this.portFile, 'utf8').trim();
            const parsed = parseInt(raw, 10);
            if (Number.isInteger(parsed) && parsed > 0) {
              this.port = parsed;
              resolve(parsed);
              return;
            }
          }
        } catch (err) {
          // Race condition while sidecar writes the file — keep polling.
        }

        if (Date.now() >= deadline) {
          reject(
            new Error(
              `Sidecar did not report a port within ${PORT_WAIT_MS}ms ` +
                `(expected port file at ${this.portFile})`
            )
          );
          return;
        }

        setTimeout(tick, PORT_POLL_INTERVAL_MS);
      };

      tick();
    });
  }

  /**
   * Gracefully terminate the sidecar.
   *  - Sends SIGTERM.
   *  - Force-kills with SIGKILL after `timeoutMs`.
   * @param {object} [opts]
   * @param {number} [opts.timeoutMs=5000]
   */
  stop(opts = {}) {
    const timeoutMs = typeof opts.timeoutMs === 'number' ? opts.timeoutMs : 5000;

    return new Promise((resolve) => {
      if (!this.proc || this.proc.exitCode !== null) {
        resolve();
        return;
      }

      let settled = false;
      const finish = () => {
        if (settled) return;
        settled = true;
        resolve();
      };

      this.proc.once('exit', finish);

      try {
        // On Windows there is no SIGTERM; .kill() sends a CTRL_BREAK_EVENT-ish
        // signal which most Python apps will handle.
        this.proc.kill('SIGTERM');
      } catch (err) {
        console.error('[sidecar] SIGTERM failed:', err);
      }

      setTimeout(() => {
        if (!settled && this.proc && this.proc.exitCode === null) {
          try {
            this.proc.kill('SIGKILL');
          } catch (err) {
            console.error('[sidecar] SIGKILL failed:', err);
          }
        }
        // Give SIGKILL a moment to take effect.
        setTimeout(finish, 250);
      }, timeoutMs);
    });
  }
}

module.exports = SidecarManager;
