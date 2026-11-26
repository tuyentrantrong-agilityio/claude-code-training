import { api } from '../../lib/api';

export type FollowUpState = 'open' | 'done';

export interface FollowUpItem {
  id: string;
  text: string;
  owner_name: string | null;
  owner_user_id: string | null;
  at_ms: number | null;
  state: FollowUpState;
  meeting_id: string;
  meeting_title: string;
}

export type FollowUpOwner = 'me' | 'all';

export function listFollowUps(owner: FollowUpOwner, state: FollowUpState) {
  return api<{ items: FollowUpItem[] }>(`/follow-ups?owner=${owner}&state=${state}`);
}

export function setFollowUpState(id: string, state: FollowUpState): Promise<void> {
  return api(`/follow-ups/${id}`, { method: 'PATCH', body: { state } });
}

export function getFollowUpCount() {
  return api<{ open_mine: number }>('/follow-ups/count');
}
