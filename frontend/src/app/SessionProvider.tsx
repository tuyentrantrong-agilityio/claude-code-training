import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api, setCsrfToken } from '../lib/api';
import { SessionContext, type Me, type SessionState } from './useMe';

export function SessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<SessionState['status']>('loading');
  const [me, setMe] = useState<Me | null>(null);

  const applyMe = useCallback((data: Me | null) => {
    setCsrfToken(data?.csrf_token ?? null);
    setMe(data);
    setStatus(data ? 'signed-in' : 'signed-out');
  }, []);

  const refresh = useCallback(async () => {
    applyMe(await api<Me>('/me').catch(() => null));
  }, [applyMe]);

  const signOut = useCallback(async () => {
    try {
      await api('/auth/sign-out', { method: 'POST' });
    } catch {
      // The session may already be gone; sign out locally either way.
    }
    applyMe(null);
  }, [applyMe]);

  useEffect(() => {
    let cancelled = false;
    void api<Me>('/me')
      .catch(() => null)
      .then((data) => {
        if (!cancelled) applyMe(data);
      });
    return () => {
      cancelled = true;
    };
  }, [applyMe]);

  const value = useMemo(() => ({ status, me, refresh, signOut }), [status, me, refresh, signOut]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
