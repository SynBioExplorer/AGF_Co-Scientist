import { useEffect, useRef, useState, useCallback } from 'react';

interface Options {
  intervalMs?: number;
  enabled?: boolean;
}

export interface PollingResult<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

export function usePolling<T>(
  fetcher: () => Promise<T>,
  { intervalMs = 2000, enabled = true }: Options = {},
): PollingResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const mountedRef = useRef(true);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const tick = useCallback(async () => {
    if (!mountedRef.current) return;
    setLoading(true);
    try {
      const next = await fetcherRef.current();
      if (mountedRef.current) {
        setData(next);
        setError(null);
      }
    } catch (e) {
      if (mountedRef.current) {
        setError(e instanceof Error ? e : new Error(String(e)));
      }
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    if (!enabled) return () => undefined;
    void tick();
    const id = window.setInterval(() => {
      void tick();
    }, intervalMs);
    return () => {
      mountedRef.current = false;
      window.clearInterval(id);
    };
  }, [enabled, intervalMs, tick]);

  return { data, error, loading, refresh: tick };
}
