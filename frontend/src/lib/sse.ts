import { apiErrorFrom, getCsrfToken } from './api';

export interface SseEvent {
  event: string;
  data: string;
}

/**
 * Incremental parser for a text/event-stream body. Feed it text chunks of any size;
 * it calls onEvent for every complete event (events end with a blank line).
 */
export function createSseParser(onEvent: (event: SseEvent) => void) {
  let buffer = '';
  let event = '';
  let data: string[] = [];

  const handleLine = (line: string) => {
    if (line === '') {
      if (data.length > 0 || event !== '') {
        onEvent({ event: event || 'message', data: data.join('\n') });
      }
      event = '';
      data = [];
      return;
    }
    if (line.startsWith(':')) return; // comment or keep-alive
    const idx = line.indexOf(':');
    const field = idx === -1 ? line : line.slice(0, idx);
    let value = idx === -1 ? '' : line.slice(idx + 1);
    if (value.startsWith(' ')) value = value.slice(1);
    if (field === 'event') event = value;
    else if (field === 'data') data.push(value);
  };

  return {
    push(chunk: string) {
      buffer += chunk;
      let match: RegExpExecArray | null;
      // A line ends at \n, \r\n or \r; hold back a trailing \r until we know what follows.
      while ((match = /\r\n|\n|\r(?=.)/s.exec(buffer))) {
        const line = buffer.slice(0, match.index);
        buffer = buffer.slice(match.index + match[0].length);
        handleLine(line);
      }
    },
    /** Call when the stream ends; handles a last line without a newline. */
    flush() {
      if (buffer !== '') {
        const line = buffer.replace(/\r$/, '');
        buffer = '';
        handleLine(line);
      }
      handleLine('');
    },
  };
}

/** POST a JSON body and read the text/event-stream answer. Resolves when the stream ends. */
export async function postEventStream(
  path: string,
  body: unknown,
  onEvent: (event: SseEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const headers: Record<string, string> = {
    Accept: 'text/event-stream',
    'Content-Type': 'application/json',
  };
  const csrf = getCsrfToken();
  if (csrf) headers['X-CSRF-Token'] = csrf;

  const response = await fetch(`/api/v1${path}`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    let parsed: unknown = null;
    try {
      parsed = await response.json();
    } catch {
      // Body was not JSON; keep the defaults.
    }
    throw apiErrorFrom(response.status, parsed);
  }
  if (!response.body) throw new Error('The server sent no stream');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = createSseParser(onEvent);
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    parser.push(decoder.decode(value, { stream: true }));
  }
  parser.push(decoder.decode());
  parser.flush();
}
