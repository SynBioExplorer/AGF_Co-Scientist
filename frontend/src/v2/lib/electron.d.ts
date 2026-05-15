export interface ElectronAPI {
  openFolder?: () => Promise<string | null>;
  openExternal?: (url: string) => Promise<void>;
  showInFolder?: (path: string) => Promise<void>;
  openMailto?: (mailtoUrl: string) => Promise<void>;
  getBackendUrl?: () => string | undefined;
  checkForUpdates?: () => Promise<{
    update_available: boolean;
    latest_version?: string;
    url?: string;
  }>;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}

export {};
