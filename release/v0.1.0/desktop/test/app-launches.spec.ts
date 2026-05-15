/**
 * Smoke test — the Electron app launches, opens a window within 10 s,
 * and exposes `window.electronAPI` to the renderer.
 *
 * Run with:
 *   npm run test:electron
 *   (equivalent: npx playwright test --config release/v0.1.0/desktop/test/playwright.config.ts)
 *
 * NOTE: requires a display (or `xvfb-run`) on Linux CI. Skipped automatically
 * in headless environments without a display server.
 */

import { test, expect, _electron as electron } from '@playwright/test';
import * as path from 'path';

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const MAIN_JS = path.join(REPO_ROOT, 'desktop', 'main.js');

test.describe('AGF Co-Scientist Electron shell', () => {
  test('launches and exposes electronAPI', async () => {
    const electronApp = await electron.launch({
      args: [MAIN_JS],
      env: {
        ...process.env,
        NODE_ENV: 'development',
        // Block the real Python sidecar from being needed; the test only
        // cares that the BrowserWindow renders.
        AGF_SKIP_SIDECAR: '1',
      },
      timeout: 30_000,
    });

    // Wait for the first window — must appear within 10 s of ready.
    const window = await Promise.race([
      electronApp.firstWindow(),
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error('window did not appear within 10s')), 10_000)
      ),
    ]);

    expect(window).toBeTruthy();

    // Renderer should see the preload bridge.
    const hasApi = await window.evaluate(
      () => typeof (window as unknown as { electronAPI?: unknown }).electronAPI !== 'undefined'
    );
    expect(hasApi).toBe(true);

    await electronApp.close();
  });
});
