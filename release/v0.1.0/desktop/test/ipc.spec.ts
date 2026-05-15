/**
 * IPC handler tests.
 *
 * We can't easily import `desktop/main.js` directly (it boots Electron
 * on import), so this test extracts the handler registration logic into
 * an isolated helper and verifies each handler:
 *
 *  - is registered with the expected channel name
 *  - delegates to the mocked `dialog` / `shell` modules with the right
 *    arguments
 *  - returns the expected shape
 */

import { test, expect } from '@playwright/test';

type Handler = (event: unknown, ...args: unknown[]) => Promise<unknown> | unknown;

interface MockIpcMain {
  handlers: Map<string, Handler>;
  handle: (channel: string, fn: Handler) => void;
}

interface MockDialog {
  showOpenDialog: (opts: unknown) => Promise<{ canceled: boolean; filePaths: string[] }>;
  showErrorBox: (title: string, content: string) => void;
}

interface MockShell {
  openExternal: (url: string) => Promise<boolean>;
  showItemInFolder: (path: string) => void;
}

/**
 * Re-implementation of `registerIpcHandlers` from `desktop/main.js`,
 * parameterised over the Electron modules so we can inject mocks.
 *
 * This mirrors the production logic 1:1; if the production handler
 * changes, this should be updated to match.
 */
function registerIpcHandlersForTest(
  ipcMain: MockIpcMain,
  dialog: MockDialog,
  shell: MockShell,
  sidecarUrl: () => string | null,
  updateChecker: () => Promise<unknown>
) {
  ipcMain.handle('dialog:openFolder', async () => {
    const result = await dialog.showOpenDialog({ properties: ['openDirectory'] });
    if (result.canceled || result.filePaths.length === 0) return null;
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

  ipcMain.handle('backend:getUrl', () => sidecarUrl());

  ipcMain.handle('app:checkForUpdates', async () => updateChecker());
}

function makeMockIpc(): MockIpcMain {
  const handlers = new Map<string, Handler>();
  return {
    handlers,
    handle(channel, fn) {
      handlers.set(channel, fn);
    },
  };
}

test.describe('IPC handlers', () => {
  test('registers every expected channel', () => {
    const ipc = makeMockIpc();
    registerIpcHandlersForTest(
      ipc,
      {
        showOpenDialog: async () => ({ canceled: true, filePaths: [] }),
        showErrorBox: () => {},
      },
      {
        openExternal: async () => true,
        showItemInFolder: () => {},
      },
      () => null,
      async () => ({ ok: true })
    );

    const expected = [
      'dialog:openFolder',
      'shell:openMailto',
      'shell:openExternal',
      'shell:showItemInFolder',
      'backend:getUrl',
      'app:checkForUpdates',
    ];
    for (const channel of expected) {
      expect(ipc.handlers.has(channel)).toBe(true);
    }
  });

  test('dialog:openFolder returns null when cancelled', async () => {
    const ipc = makeMockIpc();
    registerIpcHandlersForTest(
      ipc,
      {
        showOpenDialog: async () => ({ canceled: true, filePaths: [] }),
        showErrorBox: () => {},
      },
      { openExternal: async () => true, showItemInFolder: () => {} },
      () => null,
      async () => ({ ok: true })
    );
    const result = await ipc.handlers.get('dialog:openFolder')!({});
    expect(result).toBeNull();
  });

  test('dialog:openFolder returns first path on selection', async () => {
    const ipc = makeMockIpc();
    registerIpcHandlersForTest(
      ipc,
      {
        showOpenDialog: async () => ({
          canceled: false,
          filePaths: ['/Users/test/projects/agf'],
        }),
        showErrorBox: () => {},
      },
      { openExternal: async () => true, showItemInFolder: () => {} },
      () => null,
      async () => ({ ok: true })
    );
    const result = await ipc.handlers.get('dialog:openFolder')!({});
    expect(result).toBe('/Users/test/projects/agf');
  });

  test('shell:openMailto rejects non-mailto URLs', async () => {
    const ipc = makeMockIpc();
    registerIpcHandlersForTest(
      ipc,
      { showOpenDialog: async () => ({ canceled: true, filePaths: [] }), showErrorBox: () => {} },
      { openExternal: async () => true, showItemInFolder: () => {} },
      () => null,
      async () => ({ ok: true })
    );
    await expect(
      (ipc.handlers.get('shell:openMailto')! as Handler)({}, 'https://example.com')
    ).rejects.toThrow(/mailto/);
  });

  test('shell:openMailto delegates to shell.openExternal', async () => {
    const ipc = makeMockIpc();
    const calls: string[] = [];
    registerIpcHandlersForTest(
      ipc,
      { showOpenDialog: async () => ({ canceled: true, filePaths: [] }), showErrorBox: () => {} },
      {
        openExternal: async (url: string) => {
          calls.push(url);
          return true;
        },
        showItemInFolder: () => {},
      },
      () => null,
      async () => ({ ok: true })
    );
    const result = await ipc.handlers.get('shell:openMailto')!({}, 'mailto:test@example.com');
    expect(result).toBe(true);
    expect(calls).toEqual(['mailto:test@example.com']);
  });

  test('shell:showItemInFolder forwards the path', async () => {
    const ipc = makeMockIpc();
    const reveals: string[] = [];
    registerIpcHandlersForTest(
      ipc,
      { showOpenDialog: async () => ({ canceled: true, filePaths: [] }), showErrorBox: () => {} },
      {
        openExternal: async () => true,
        showItemInFolder: (p: string) => reveals.push(p),
      },
      () => null,
      async () => ({ ok: true })
    );
    const result = await ipc.handlers.get('shell:showItemInFolder')!({}, '/tmp/file.txt');
    expect(result).toBe(true);
    expect(reveals).toEqual(['/tmp/file.txt']);
  });

  test('backend:getUrl reflects sidecar state', async () => {
    const ipc = makeMockIpc();
    let url: string | null = null;
    registerIpcHandlersForTest(
      ipc,
      { showOpenDialog: async () => ({ canceled: true, filePaths: [] }), showErrorBox: () => {} },
      { openExternal: async () => true, showItemInFolder: () => {} },
      () => url,
      async () => ({ ok: true })
    );

    expect(await ipc.handlers.get('backend:getUrl')!({})).toBeNull();
    url = 'http://127.0.0.1:54321';
    expect(await ipc.handlers.get('backend:getUrl')!({})).toBe('http://127.0.0.1:54321');
  });

  test('app:checkForUpdates returns the checker result', async () => {
    const ipc = makeMockIpc();
    registerIpcHandlersForTest(
      ipc,
      { showOpenDialog: async () => ({ canceled: true, filePaths: [] }), showErrorBox: () => {} },
      { openExternal: async () => true, showItemInFolder: () => {} },
      () => null,
      async () => ({ ok: true, updateInfo: { version: '1.2.3' } })
    );
    const result = await ipc.handlers.get('app:checkForUpdates')!({});
    expect(result).toEqual({ ok: true, updateInfo: { version: '1.2.3' } });
  });
});
