import { useEffect, useState, useCallback } from 'react';

type ThemeMode = 'light' | 'dark' | 'system';

const STORAGE_KEY = 'agf:theme';

function applyTheme(mode: ThemeMode): void {
  const root = document.documentElement;
  if (mode === 'system') {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    root.classList.toggle('dark', prefersDark);
  } else {
    root.classList.toggle('dark', mode === 'dark');
  }
}

export function useTheme(): {
  mode: ThemeMode;
  setMode: (m: ThemeMode) => void;
  effective: 'light' | 'dark';
} {
  const [mode, setModeState] = useState<ThemeMode>(() => {
    if (typeof window === 'undefined') return 'system';
    return (window.localStorage.getItem(STORAGE_KEY) as ThemeMode | null) ?? 'system';
  });
  const [effective, setEffective] = useState<'light' | 'dark'>('light');

  useEffect(() => {
    applyTheme(mode);
    const isDark = document.documentElement.classList.contains('dark');
    setEffective(isDark ? 'dark' : 'light');
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (): void => {
      if (mode === 'system') {
        applyTheme('system');
        setEffective(window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
      }
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [mode]);

  const setMode = useCallback((m: ThemeMode) => {
    setModeState(m);
    window.localStorage.setItem(STORAGE_KEY, m);
  }, []);

  return { mode, setMode, effective };
}

export type { ThemeMode };
