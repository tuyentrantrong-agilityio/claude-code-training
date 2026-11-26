import { createContext, useContext } from 'react';

export interface FollowUpCountState {
  count: number;
  /** Fetch the open follow-up count again (call after follow-ups change). */
  refresh: () => void;
}

export const FollowUpCountContext = createContext<FollowUpCountState>({
  count: 0,
  refresh: () => {},
});

export function useFollowUpCount(): FollowUpCountState {
  return useContext(FollowUpCountContext);
}
