import { useCallback, useEffect, useState } from 'react';

interface Slot<T> {
  load: () => Promise<T>;
  data: T | null;
  error: unknown;
}

/**
 * Load data with the given function (keep it stable with useCallback).
 * A new function starts a new load; reload() repeats the current one and keeps old data meanwhile.
 */
export function useLoad<T>(load: () => Promise<T>) {
  const [slot, setSlot] = useState<Slot<T> | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;
    load()
      .then((data) => {
        if (!cancelled) setSlot({ load, data, error: null });
      })
      .catch((error: unknown) => {
        if (!cancelled) setSlot({ load, data: null, error });
      });
    return () => {
      cancelled = true;
    };
  }, [load, version]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  const update = useCallback(
    (change: (data: T) => T) =>
      setSlot((s) => (s && s.data !== null ? { ...s, data: change(s.data) } : s)),
    [],
  );

  const current = slot?.load === load ? slot : null;
  return {
    data: current?.data ?? null,
    error: current?.error ?? null,
    loading: !current,
    reload,
    update,
  };
}

export function errorText(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong';
}
