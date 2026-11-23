import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { ToastContext } from './toast-context';

export const TOAST_MS = 2500;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const show = useCallback((text: string) => {
    clearTimeout(timer.current);
    setMessage(text);
    timer.current = setTimeout(() => setMessage(null), TOAST_MS);
  }, []);

  useEffect(() => () => clearTimeout(timer.current), []);

  return (
    <ToastContext.Provider value={show}>
      {children}
      {message && (
        <div
          role="status"
          className="fixed bottom-5 left-1/2 z-[70] max-w-[90vw] -translate-x-1/2 rounded-xl bg-ink px-4 py-2.5 font-medium text-bg shadow-pop"
        >
          {message}
        </div>
      )}
    </ToastContext.Provider>
  );
}
