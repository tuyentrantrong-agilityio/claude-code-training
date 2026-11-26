import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { StrictMode } from 'react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { ToastProvider } from '../../components/Toast';
import { setCsrfToken } from '../../lib/api';
import AskPage from './AskPage';

type Handler = (init: RequestInit) => Response | Promise<Response>;

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

/** Fetch mock keyed by "METHOD /path"; records every call. */
function mockApi(routes: Record<string, Handler>) {
  const calls: { key: string; init: RequestInit }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const key = `${init.method ?? 'GET'} ${String(input).replace(/^\/api\/v1/, '')}`;
      calls.push({ key, init });
      const route = routes[key];
      if (!route) return json({ error: { code: 'not_mocked', message: key } }, 404);
      return route(init);
    }),
  );
  return {
    count: (key: string) => calls.filter((c) => c.key === key).length,
    bodies: (key: string) =>
      calls.filter((c) => c.key === key).map((c) => JSON.parse(String(c.init.body)) as unknown),
    calls,
  };
}

const enc = new TextEncoder();
const ev = (name: string, data: unknown) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;

/** A stream response the test can feed chunk by chunk. */
function liveStream(signal?: AbortSignal | null) {
  let ctrl!: ReadableStreamDefaultController<Uint8Array>;
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      ctrl = c;
    },
  });
  signal?.addEventListener('abort', () => {
    try {
      ctrl.error(new DOMException('Aborted', 'AbortError'));
    } catch {
      // Already closed.
    }
  });
  return {
    response: new Response(body, { status: 200 }),
    push: (text: string) => act(async () => ctrl.enqueue(enc.encode(text))),
    close: () => act(async () => ctrl.close()),
  };
}

/** A complete stream response from fixed chunks. */
function doneStream(chunks: string[]) {
  return new Response(
    new ReadableStream<Uint8Array>({
      start(c) {
        chunks.forEach((t) => c.enqueue(enc.encode(t)));
        c.close();
      },
    }),
    { status: 200 },
  );
}

const conv = (id: string, title = 'New chat', scope: string | null = null) => ({
  id,
  title,
  scope_meeting_id: scope,
  updated_at: '2026-11-20T10:00:00Z',
});

function Where() {
  const loc = useLocation();
  return <div data-testid="where">{loc.pathname + loc.search}</div>;
}

function renderAsk(path = '/ask', strict = false) {
  const tree = (
    <MemoryRouter initialEntries={[path]}>
      <ToastProvider>
        <Where />
        <Routes>
          <Route path="/ask" element={<AskPage />} />
          <Route path="*" element={null} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>
  );
  return render(strict ? <StrictMode>{tree}</StrictMode> : tree);
}

const where = () => screen.getByTestId('where').textContent;
const box = () => screen.getByPlaceholderText('Ask anything about your meetings');

beforeEach(() => setCsrfToken('csrf-123'));
afterEach(() => {
  vi.unstubAllGlobals();
  setCsrfToken(null);
});

describe('AskPage', () => {
  it('shows the header, the empty list text and the starter questions', async () => {
    mockApi({ 'GET /conversations': () => json({ items: [] }) });
    renderAsk();
    expect(screen.getByRole('heading', { level: 1, name: 'Ask' })).toBeInTheDocument();
    expect(
      screen.getByText(
        'Ask across all your meetings. Every answer points to the moment it came from.',
      ),
    ).toBeInTheDocument();
    expect(await screen.findByText('Your chats will be listed here.')).toBeInTheDocument();
    expect(screen.getByText('What would you like to know?')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'List my open follow-ups' })).toBeInTheDocument();
  });

  it('starter creates a chat, shows Thinking, streams tokens, then citation chips', async () => {
    let stream!: ReturnType<typeof liveStream>;
    const api = mockApi({
      'GET /conversations': () => json({ items: [] }),
      'POST /conversations': () => json(conv('c1'), 201),
      'POST /conversations/c1/messages': (init) => {
        stream = liveStream(init.signal);
        return stream.response;
      },
    });
    renderAsk();
    fireEvent.click(await screen.findByRole('button', { name: 'List my open follow-ups' }));

    expect(await screen.findByText('Thinking...')).toBeInTheDocument();
    expect(screen.getByText('List my open follow-ups', { selector: 'p' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled();
    await waitFor(() => expect(where()).toBe('/ask?c=c1'));
    expect(api.bodies('POST /conversations')).toEqual([{ scope_meeting_id: null }]);
    expect(api.bodies('POST /conversations/c1/messages')).toEqual([
      { text: 'List my open follow-ups' },
    ]);
    const init = api.calls.find((c) => c.key === 'POST /conversations')!.init;
    expect((init.headers as Record<string, string>)['X-CSRF-Token']).toBe('csrf-123');

    await stream.push(ev('token', { text: 'You have ' }));
    expect(await screen.findByText('You have')).toBeInTheDocument();
    expect(screen.queryByText('Thinking...')).not.toBeInTheDocument();
    await stream.push(ev('token', { text: 'two.' }));
    expect(await screen.findByText('You have two.')).toBeInTheDocument();
    await stream.push(
      ev('citations', {
        items: [{ meeting_id: 'm1', meeting_title: 'Weekly sync', at_ms: 65000 }],
      }),
    );
    await stream.push(ev('done', { message_id: 'a1' }));
    await stream.close();

    const sources = await screen.findByRole('list', { name: 'Sources' });
    expect(within(sources).getByRole('link', { name: 'Weekly sync' })).toHaveAttribute(
      'href',
      '/meetings/m1?t=65',
    );
    fireEvent.click(within(sources).getByRole('button', { name: 'Jump to 01:05' }));
    await waitFor(() => expect(where()).toBe('/meetings/m1?t=65'));
  });

  it('Enter submits, Shift+Enter does not', async () => {
    const api = mockApi({
      'GET /conversations': () => json({ items: [] }),
      'POST /conversations': () => json(conv('c1'), 201),
      'POST /conversations/c1/messages': () =>
        doneStream([ev('token', { text: 'Ok' }), ev('done', { message_id: 'a1' })]),
    });
    renderAsk();
    await screen.findByText('Your chats will be listed here.');
    fireEvent.change(box(), { target: { value: 'hello' } });
    fireEvent.keyDown(box(), { key: 'Enter', shiftKey: true });
    expect(api.count('POST /conversations')).toBe(0);
    fireEvent.keyDown(box(), { key: 'Enter' });
    expect(await screen.findByText('Ok')).toBeInTheDocument();
    expect(api.count('POST /conversations/c1/messages')).toBe(1);
    expect(box()).toHaveValue('');
  });

  it('shows the error with Retry and resends the same question', async () => {
    let n = 0;
    const api = mockApi({
      'GET /conversations': () => json({ items: [] }),
      'POST /conversations': () => json(conv('c1'), 201),
      'POST /conversations/c1/messages': () => {
        n += 1;
        return n === 1
          ? doneStream([ev('error', { code: 'llm_failed', message: 'The model is busy' })])
          : doneStream([ev('token', { text: 'Second try' }), ev('done', { message_id: 'a2' })]);
      },
    });
    renderAsk();
    fireEvent.click(await screen.findByRole('button', { name: 'List my open follow-ups' }));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('The model is busy');
    fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('Second try')).toBeInTheDocument();
    expect(api.bodies('POST /conversations/c1/messages')).toEqual([
      { text: 'List my open follow-ups' },
      { text: 'List my open follow-ups' },
    ]);
    expect(api.count('POST /conversations')).toBe(1);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('?q= creates a chat and sends once, even in StrictMode, then drops q', async () => {
    const api = mockApi({
      'GET /conversations': () => json({ items: [] }),
      'POST /conversations': () => json(conv('c1'), 201),
      'POST /conversations/c1/messages': () =>
        doneStream([ev('token', { text: 'Answer' }), ev('done', { message_id: 'a1' })]),
    });
    renderAsk('/ask?q=what%20is%20next', true);
    expect(await screen.findByText('Answer')).toBeInTheDocument();
    expect(api.count('POST /conversations')).toBe(1);
    expect(api.bodies('POST /conversations/c1/messages')).toEqual([{ text: 'what is next' }]);
    expect(where()).toBe('/ask?c=c1');
  });

  it('?meeting= shows the scope banner and creates a scoped chat', async () => {
    const api = mockApi({
      'GET /conversations': () => json({ items: [] }),
      'GET /meetings/m7': () => json({ id: 'm7', title: 'Design review', participants: [] }),
      'POST /conversations': () => json(conv('c1', 'New chat', 'm7'), 201),
      'POST /conversations/c1/messages': () =>
        doneStream([ev('token', { text: 'Scoped' }), ev('done', { message_id: 'a1' })]),
    });
    renderAsk('/ask?meeting=m7');
    expect(await screen.findByText('Design review')).toBeInTheDocument();
    expect(screen.getByText(/Asking about:/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ask across all meetings' })).toHaveAttribute(
      'href',
      '/ask',
    );
    fireEvent.click(screen.getByRole('button', { name: 'List my open follow-ups' }));
    expect(await screen.findByText('Scoped')).toBeInTheDocument();
    expect(api.bodies('POST /conversations')).toEqual([{ scope_meeting_id: 'm7' }]);
    expect(where()).toBe('/ask?c=c1');
    expect(screen.getByText('Design review')).toBeInTheDocument();
  });

  it('?q= with ?meeting= sends a scoped question', async () => {
    const api = mockApi({
      'GET /conversations': () => json({ items: [] }),
      'GET /meetings/m7': () => json({ id: 'm7', title: 'Design review', participants: [] }),
      'POST /conversations': () => json(conv('c1', 'New chat', 'm7'), 201),
      'POST /conversations/c1/messages': () => doneStream([ev('done', { message_id: 'a1' })]),
    });
    renderAsk('/ask?q=Summarize%20this%20meeting&meeting=m7');
    await waitFor(() => expect(api.count('POST /conversations/c1/messages')).toBe(1));
    expect(api.bodies('POST /conversations')).toEqual([{ scope_meeting_id: 'm7' }]);
    expect(where()).toBe('/ask?c=c1');
  });

  it('lists chats, switches between them and deletes one after confirming', async () => {
    let items = [conv('c1', 'First question'), conv('c2', 'Second question')];
    const api = mockApi({
      'GET /conversations': () => json({ items }),
      'GET /conversations/c1': () =>
        json({
          ...conv('c1', 'First question'),
          messages: [
            {
              id: 'u1',
              role: 'user',
              text: 'First question',
              status: 'done',
              created_at: 't',
              citations: [],
            },
            {
              id: 'a1',
              role: 'assistant',
              text: 'First answer',
              status: 'done',
              created_at: 't',
              citations: [{ meeting_id: 'm1', meeting_title: 'Sync', at_ms: 5000 }],
            },
          ],
        }),
      'GET /conversations/c2': () =>
        json({
          ...conv('c2', 'Second question'),
          messages: [
            {
              id: 'u2',
              role: 'user',
              text: 'Second question',
              status: 'done',
              created_at: 't',
              citations: [],
            },
            {
              id: 'a2',
              role: 'assistant',
              text: '',
              status: 'failed',
              created_at: 't',
              citations: [],
            },
          ],
        }),
      'DELETE /conversations/c1': () => {
        items = [conv('c2', 'Second question')];
        return new Response(null, { status: 204 });
      },
    });
    renderAsk('/ask?c=c1');
    expect(await screen.findByText('First answer')).toBeInTheDocument();
    const nav = screen.getByRole('complementary', { name: 'Chats' });
    expect(within(nav).getByRole('link', { name: 'First question' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(within(nav).getByRole('link', { name: 'Second question' })).not.toHaveAttribute(
      'aria-current',
    );

    fireEvent.click(within(nav).getByRole('link', { name: 'Second question' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('could not be completed');
    expect(screen.queryByText('First answer')).not.toBeInTheDocument();
    expect(where()).toBe('/ask?c=c2');

    fireEvent.click(within(nav).getByRole('button', { name: 'Delete chat Second question' }));
    fireEvent.click(within(nav).getByRole('button', { name: 'Delete chat First question' }));
    expect(api.count('DELETE /conversations/c1')).toBe(0);
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }));
    expect(api.count('DELETE /conversations/c1')).toBe(0);

    fireEvent.click(within(nav).getByRole('button', { name: 'Delete chat First question' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(api.count('DELETE /conversations/c1')).toBe(1));
    await waitFor(() =>
      expect(within(nav).queryByRole('link', { name: 'First question' })).not.toBeInTheDocument(),
    );
  });

  it('deleting the open chat returns to a new chat', async () => {
    mockApi({
      'GET /conversations': () => json({ items: [conv('c1', 'Only chat')] }),
      'GET /conversations/c1': () => json({ ...conv('c1', 'Only chat'), messages: [] }),
      'DELETE /conversations/c1': () => new Response(null, { status: 204 }),
    });
    renderAsk('/ask?c=c1');
    fireEvent.click(await screen.findByRole('button', { name: 'Delete chat Only chat' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(where()).toBe('/ask'));
    expect(await screen.findByText('What would you like to know?')).toBeInTheDocument();
  });

  it('Stop aborts the stream and keeps the text so far', async () => {
    let signal: AbortSignal | null | undefined;
    let stream!: ReturnType<typeof liveStream>;
    mockApi({
      'GET /conversations': () => json({ items: [] }),
      'POST /conversations': () => json(conv('c1'), 201),
      'POST /conversations/c1/messages': (init) => {
        signal = init.signal;
        stream = liveStream(init.signal);
        return stream.response;
      },
    });
    renderAsk();
    fireEvent.click(await screen.findByRole('button', { name: 'List my open follow-ups' }));
    await screen.findByText('Thinking...');
    await stream.push(ev('token', { text: 'Partial' }));
    await screen.findByText('Partial');
    fireEvent.click(screen.getByRole('button', { name: 'Stop' }));
    await waitFor(() => expect(signal?.aborted).toBe(true));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Stop' })).toBeNull());
    expect(screen.getByText('Partial')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    fireEvent.change(box(), { target: { value: 'again' } });
    expect(screen.getByRole('button', { name: 'Ask' })).toBeEnabled();
  });
});
