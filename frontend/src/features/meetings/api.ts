import { api, apiErrorFrom, getCsrfToken } from '../../lib/api';

export type MeetingStatus = 'ready' | 'processing' | 'incomplete';
export type Stage = 'uploading' | 'transcribing' | 'summarizing' | 'filing';
export type Language = 'en' | 'vi';

export interface MeetingSummary {
  id: string;
  title: string;
  status: MeetingStatus;
  stage: string | null;
  error: string | null;
  source: string;
  platform: string;
  language: string;
  started_at: string | null;
  duration_ms: number | null;
  summary_preview: string | null;
  participants: { id: string; display_name: string }[];
  folder: { id: string; name: string } | null;
}

export type StatusCounts = Record<MeetingStatus, number>;

export interface MeetingList {
  items: MeetingSummary[];
  next_cursor: string | null;
  meta: { counts: StatusCounts };
}

export interface ListParams {
  status?: MeetingStatus;
  q?: string;
  limit?: number;
  cursor?: string | null;
}

export function listMeetings(params: ListParams = {}): Promise<MeetingList> {
  const qs = new URLSearchParams();
  if (params.status) qs.set('status', params.status);
  if (params.q) qs.set('q', params.q);
  if (params.limit) qs.set('limit', String(params.limit));
  if (params.cursor) qs.set('cursor', params.cursor);
  const query = qs.toString();
  return api<MeetingList>(`/meetings${query ? `?${query}` : ''}`);
}

export function deleteMeeting(id: string): Promise<void> {
  return api(`/meetings/${id}`, { method: 'DELETE' });
}

export function retryMeeting(id: string): Promise<void> {
  return api(`/meetings/${id}/retry`, { method: 'POST' });
}

export interface UploadInput {
  file: File;
  language: Language;
  title?: string;
}

/** Multipart upload with progress (fraction 0..1), using XHR for upload events. */
export function uploadMeeting(
  input: UploadInput,
  onProgress?: (fraction: number) => void,
): Promise<MeetingSummary> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append('file', input.file);
    form.append('language', input.language);
    if (input.title) form.append('title', input.title);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/v1/meetings/uploads');
    xhr.withCredentials = true;
    xhr.setRequestHeader('Accept', 'application/json');
    const token = getCsrfToken();
    if (token) xhr.setRequestHeader('X-CSRF-Token', token);

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
    };
    xhr.onerror = () => reject(new Error('Upload failed. Check your connection and try again.'));
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        // Not JSON; fall back to the default error message.
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as MeetingSummary);
      else reject(apiErrorFrom(xhr.status, body));
    };
    xhr.send(form);
  });
}

export interface MeetingEventHandlers {
  onStage?: (stage: string) => void;
  onStatus?: (status: MeetingStatus, error: string | null) => void;
}

/** Subscribe to processing events; returns an unsubscribe function. */
export function subscribeMeetingEvents(id: string, handlers: MeetingEventHandlers): () => void {
  const source = new EventSource(`/api/v1/meetings/${id}/events`, { withCredentials: true });

  source.addEventListener('stage', (e) => {
    try {
      const data = JSON.parse((e as MessageEvent<string>).data) as { stage: string };
      handlers.onStage?.(data.stage);
    } catch {
      // Ignore malformed events.
    }
  });

  source.addEventListener('status', (e) => {
    try {
      const data = JSON.parse((e as MessageEvent<string>).data) as {
        status: MeetingStatus;
        error?: string | null;
      };
      handlers.onStatus?.(data.status, data.error ?? null);
      // The stream ends at a final status; stop the browser from reconnecting.
      if (data.status !== 'processing') source.close();
    } catch {
      // Ignore malformed events.
    }
  });

  return () => source.close();
}
