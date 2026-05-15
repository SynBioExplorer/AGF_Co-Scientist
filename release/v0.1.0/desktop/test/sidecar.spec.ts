/**
 * Unit test — SidecarManager port detection.
 *
 * Strategy: replace the bundled Python binary with a Node script that
 * writes a known port to `<userData>/port.txt` and then sleeps. The
 * SidecarManager should pick that port up via its file-polling loop.
 */

import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';

// eslint-disable-next-line @typescript-eslint/no-var-requires
const SidecarManager = require('../sidecar');

function makeTmpDir(prefix: string): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

test.describe('SidecarManager', () => {
  test('reads port from port.txt written by the child process', async () => {
    const userDataDir = makeTmpDir('agf-sidecar-');
    const fakeBackend = path.join(userDataDir, 'fake-backend.js');
    const fakePort = 51234;

    // Tiny Node program that mimics the Python sidecar: writes its port
    // then idles until stdin closes / signal received.
    fs.writeFileSync(
      fakeBackend,
      `
        const fs = require('fs');
        const path = require('path');
        const portFile = path.join(process.env.AGF_DATA_DIR, 'port.txt');
        fs.writeFileSync(portFile, '${fakePort}');
        process.stdout.write('Uvicorn running on http://127.0.0.1:${fakePort}\\n');
        setInterval(() => {}, 1000);
      `
    );

    const mgr = new SidecarManager({ userDataDir, isDev: true });

    // Monkey-patch _spawnDev to invoke our fake backend with `node`
    // instead of `python -m uvicorn`. This keeps the file-polling path
    // exercised end-to-end.
    const { spawn } = require('child_process');
    mgr._spawnDev = function () {
      this.proc = spawn(process.execPath, [fakeBackend], {
        env: {
          ...process.env,
          AGF_DATA_DIR: userDataDir,
        },
        stdio: ['ignore', 'pipe', 'pipe'],
      });
      this._wireProcessLogging();
    };

    try {
      const url = await mgr.start();
      expect(url).toBe(`http://127.0.0.1:${fakePort}`);
      expect(mgr.getUrl()).toBe(`http://127.0.0.1:${fakePort}`);
    } finally {
      await mgr.stop({ timeoutMs: 1000 });
      try {
        fs.rmSync(userDataDir, { recursive: true, force: true });
      } catch {
        /* ignore */
      }
    }
  });

  test('rejects when no port appears within the timeout', async () => {
    const userDataDir = makeTmpDir('agf-sidecar-noport-');

    const mgr = new SidecarManager({ userDataDir, isDev: true });

    // Replace spawner with a no-op so no port file is ever written.
    mgr._spawnDev = function () {
      const { spawn } = require('child_process');
      this.proc = spawn(process.execPath, ['-e', 'setInterval(()=>{}, 1000)'], {
        stdio: ['ignore', 'pipe', 'pipe'],
      });
      this._wireProcessLogging();
    };

    // Shorten the wait window via reflection on the module constant.
    // We can't easily change the module-level PORT_WAIT_MS, so we just
    // accept the 15 s wait and mark the test as long-running.
    test.setTimeout(20_000);

    let caught: Error | null = null;
    try {
      await mgr.start();
    } catch (err) {
      caught = err as Error;
    } finally {
      await mgr.stop({ timeoutMs: 1000 });
      try {
        fs.rmSync(userDataDir, { recursive: true, force: true });
      } catch {
        /* ignore */
      }
    }

    expect(caught).not.toBeNull();
    expect(caught!.message).toMatch(/did not report a port/i);
  });
});
