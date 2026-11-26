import { api } from '../../lib/api';
import { postEventStream, type SseEvent } from '../../lib/sse';

export interface Conversation {
  id: string;
  title: string;
  scope_meeting_id: string | null;
  updated_at: string;
}

export interface Citation {
  meeting_id: string;
  meeting_title: string;
  at_ms: number;
}

export type MessageStatus = 'streaming' | 'done' | 'failed';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  status: MessageStatus;
  created_at: string;
  citations: Citation[];
}

export interface ConversationDetail {
  id: string;
  title: string;
  scope_meeting_id: string | null;
  messages: ChatMessage[];
}

export const listConversations = () => api<{ items: Conversation[] }>('/conversations');

export const createConversation = (scopeMeetingId: string | null) =>
  api<Conversation>('/conversations', {
    method: 'POST',
    body: { scope_meeting_id: scopeMeetingId },
  });

export const getConversation = (id: string) => api<ConversationDetail>(`/conversations/${id}`);

export const deleteConversation = (id: string): Promise<void> =>
  api(`/conversations/${id}`, { method: 'DELETE' });

export interface AnswerHandlers {
  onToken: (text: string) => void;
  onCitations: (items: Citation[]) => void;
  onDone: (messageId: string) => void;
  onError: (message: string) => void;
}

function parseData(event: SseEvent): Record<string, unknown> | null {
  try {
    return JSON.parse(event.data) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/** Send a question and stream the answer. Resolves when the stream ends. */
export function sendMessage(
  conversationId: string,
  text: string,
  handlers: AnswerHandlers,
  signal?: AbortSignal,
): Promise<void> {
  return postEventStream(
    `/conversations/${conversationId}/messages`,
    { text },
    (event) => {
      const data = parseData(event);
      if (!data) return;
      if (event.event === 'token') handlers.onToken(String(data.text ?? ''));
      else if (event.event === 'citations') {
        handlers.onCitations((data.items as Citation[] | undefined) ?? []);
      } else if (event.event === 'done') handlers.onDone(String(data.message_id ?? ''));
      else if (event.event === 'error') {
        handlers.onError(String(data.message ?? 'Something went wrong'));
      }
    },
    signal,
  );
}
