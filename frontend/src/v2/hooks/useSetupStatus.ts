import { useEffect, useState } from 'react';
import { getSetupStatus } from '../lib/api';
import type { SetupStatus } from '../lib/types';

export interface UseSetupStatusResult {
  status: SetupStatus | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

export function useSetupStatus(): UseSetupStatusResult {
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const refresh = async (): Promise<void> => {
    setLoading(true);
    try {
      const s = await getSetupStatus();
      setStatus(s);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  return { status, loading, refresh };
}
