import { createSseParser, postEventStream, type SseEvent } from './sse';
import { setCsrfToken } from './api';

function parse(chunks: string[]): SseEvent[] {
  const out: SseEvent[] = [];
  const parser = createSseParser((e) => out.push(e));
  chunks.forEach((c) => parser.push(c));
  parser.flush();
  return out;
}

describe('createSseParser', () => {
  it('parses events in one chunk', () => {
    expect(parse(['event: token\ndata: {"text":"Hi"}\n\nevent: done\ndata: {}\n\n'])).toEqual([
      { event: 'token', data: '{"text":"Hi"}' },
      { event: 'done', data: '{}' },
    ]);
  });

  it('handles chunks split in the middle of lines and fields', () => {
    expect(
      parse(['eve', 'nt: tok', 'en\nda', 'ta: {"text":"A"}\n', '\nevent: done\nda', 'ta: {}\n\n']),
    ).toEqual([
      { event: 'token', data: '{"text":"A"}' },
      { event: 'done', data: '{}' },
    ]);
  });

  it('handles CRLF split between chunks', () => {
    expect(parse(['event: token\r', '\ndata: x\r\n\r', '\n'])).toEqual([
      { event: 'token', data: 'x' },
    ]);
  });

  it('joins multiple data lines, skips comments, defaults the name', () => {
    expect(parse([': ping\n\ndata: a\ndata: b\n\n'])).toEqual([{ event: 'message', data: 'a\nb' }]);
  });

  it('flushes a final event without a trailing blank line', () => {
    expect(parse(['event: done\ndata: {}'])).toEqual([{ event: 'done', data: '{}' }]);
  });
});

describe('postEventStream', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    setCsrfToken(null);
  });

  it('sends the CSRF header and reads events across chunks', async () => {
    setCsrfToken('csrf-9');
    const enc = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(enc.encode('event: token\ndata: {"te'));
        c.enqueue(enc.encode('xt":"Yo"}\n\n'));
        c.close();
      },
    });
    const spy = vi.fn(async () => new Response(body, { status: 200 }));
    vi.stubGlobal('fetch', spy);
    const events: SseEvent[] = [];
    await postEventStream('/x', { a: 1 }, (e) => events.push(e));
    expect(events).toEqual([{ event: 'token', data: '{"text":"Yo"}' }]);
    const init = (spy.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect((init.headers as Record<string, string>)['X-CSRF-Token']).toBe('csrf-9');
  });

  it('throws an ApiError for a non-2xx response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ error: { code: 'nope', message: 'No way' } }), {
            status: 403,
          }),
      ),
    );
    await expect(postEventStream('/x', {}, () => undefined)).rejects.toThrow('No way');
  });
});
