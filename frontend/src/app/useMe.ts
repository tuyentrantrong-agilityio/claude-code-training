import { createContext, useContext } from 'react';

export type Role = 'owner' | 'member';

export interface Me {
  user: { id: string; email: string; name: string };
  organization: { id: string; name: string };
  role: Role;
  csrf_token: string;
}

export interface SessionState {
  status: 'loading' | 'signed-in' | 'signed-out';
  me: Me | null;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
}

export const SessionContext = createContext<SessionState | null>(null);

export function useMe(): SessionState {
  const value = useContext(SessionContext);
  if (!value) throw new Error('useMe must be used inside SessionProvider');
  return value;
}
