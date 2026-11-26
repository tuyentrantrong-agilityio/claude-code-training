import { api } from '../../lib/api';
import type { FollowUpItem } from '../follow-ups/api';
import type { MeetingSummary } from '../meetings/api';

export interface HomeData {
  needs_you: FollowUpItem[];
  recent_meetings: MeetingSummary[];
  has_any_meeting: boolean;
}

export const getHome = () => api<HomeData>('/home');
