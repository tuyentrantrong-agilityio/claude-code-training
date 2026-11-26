import { api } from '../../lib/api';
import type { FollowUpState } from '../follow-ups/api';

const BASE = '/api/v1';

export interface MeetingDetail {
  id: string;
  title: string;
  status: 'ready' | 'processing' | 'incomplete';
  stage: string | null;
  error: string | null;
  source: string;
  platform: string;
  language: string;
  started_at: string | null;
  duration_ms: number | null;
  participants: { id: string; display_name: string }[];
}

export interface RecapFollowUp {
  id: string;
  text: string;
  owner_name: string | null;
  owner_user_id: string | null;
  at_ms: number | null;
  state: FollowUpState;
}

export interface Recap {
  summary: string | null;
  summary_edited_at: string | null;
  follow_ups: RecapFollowUp[];
  key_points: { id: string; title: string; text: string; at_ms: number | null }[];
  chapters: { id: string; title: string; at_ms: number }[];
  highlights: { id: string; text: string; at_ms: number | null }[];
  questions: { id: string; text: string; at_ms: number | null }[];
}

export interface Segment {
  id: string;
  seq: number;
  start_ms: number;
  end_ms: number;
  participant_id: string | null;
  speaker: string | null;
  text: string;
}

export interface Person {
  participant_id: string;
  display_name: string;
  speaker_label: string | null;
  talk_ms: number;
  /** Fraction of the talk time, 0 to 1. */
  share: number;
}

export const getMeeting = (id: string) => api<MeetingDetail>(`/meetings/${id}`);
export const getRecap = (id: string) => api<Recap>(`/meetings/${id}/recap`);
export const getTranscript = (id: string) =>
  api<{ segments: Segment[] }>(`/meetings/${id}/transcript`);
export const getPeople = (id: string) => api<{ people: Person[] }>(`/meetings/${id}/people`);

export const renameMeeting = (id: string, title: string): Promise<void> =>
  api(`/meetings/${id}`, { method: 'PATCH', body: { title } });
export const saveSummary = (id: string, summary: string): Promise<void> =>
  api(`/meetings/${id}`, { method: 'PATCH', body: { summary } });
export const renameParticipant = (id: string, pid: string, display_name: string): Promise<void> =>
  api(`/meetings/${id}/participants/${pid}`, { method: 'PATCH', body: { display_name } });

export const audioUrl = (id: string) => `${BASE}/meetings/${id}/audio`;
export const transcriptExportUrl = (id: string) => `${BASE}/meetings/${id}/export/transcript.txt`;
export const recapExportUrl = (id: string) => `${BASE}/meetings/${id}/export/recap.md`;
