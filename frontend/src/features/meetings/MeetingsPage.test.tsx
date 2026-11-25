import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { ToastProvider } from '../../components/Toast';
import { uploadMeeting, type MeetingSummary, type StatusCounts } from './api';
import MeetingsPage from './MeetingsPage';

vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  uploadMeeting: vi.fn(),
}));

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  withCredentials: boolean;
  closed = false;
  listeners: Record<string, ((e: { data: string }) => void)[]> = {};

  constructor(url: string, init?: { withCredentials?: boolean }) {
    this.url = url;
    this.withCredentials = init?.withCredentials ?? false;
    FakeEventSource.instances.push(this);
  }
  addEventListener(type: string, fn: (e: { data: string }) => void) {
    (this.listeners[type] ??= []).push(fn);
  }
  close() {
    this.closed = true;
  }
  emit(type: string, data: unknown) {
    for (const fn of this.listeners[type] ?? []) fn({ data: JSON.stringify(data) });
  }
}

function meeting(over: Partial<MeetingSummary> & { id: string; title: string }): MeetingSummary {
  return {
    status: 'ready',
    stage: null,
    error: null,
    source: 'upload',
    platform: 'file',
    language: 'en',
    started_at: '2026-11-19T12:00:00Z',
    duration_ms: 60000,
    summary_preview: null,
    participants: [],
    folder: null,
    ...over,
  };
}

const ready1 = meeting({ id: 'r1', title: 'Weekly sync', summary_preview: 'We shipped it.' });
const proc1 = meeting({
  id: 'p1',
  title: 'Design review',
  status: 'processing',
  stage: 'transcribing',
});
const inc1 = meeting({
  id: 'i1',
  title: 'Broken call',
  status: 'incomplete',
  error: 'Lost audio.',
});

interface Backend {
  counts: StatusCounts;
  byStatus: Record<string, MeetingSummary[]>;
  next?: string | null;
}

function mockApi(backend: Backend) {
  const spy = vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), 'http://x');
    const status = url.searchParams.get('status') ?? 'ready';
    const cursor = url.searchParams.get('cursor');
    const body = {
      items: backend.byStatus[cursor ? `${status}:${cursor}` : status] ?? [],
      next_cursor: cursor ? null : (backend.next ?? null),
      meta: { counts: backend.counts },
    };
    return new Response(JSON.stringify(body), { status: 200 });
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}

function urlsOf(spy: ReturnType<typeof mockApi>): URL[] {
  return spy.mock.calls.map(([input]) => new URL(String(input), 'http://x'));
}

function Where() {
  const loc = useLocation();
  return <output data-testid="where">{loc.pathname + loc.search}</output>;
}

function renderPage(entry = '/meetings') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <ToastProvider>
        <MeetingsPage />
        <Where />
      </ToastProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal('EventSource', FakeEventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.mocked(uploadMeeting).mockReset();
});

const counts = { ready: 1, processing: 1, incomplete: 1 };
const basic: Backend = {
  counts,
  byStatus: { ready: [ready1], processing: [proc1], incomplete: [inc1] },
};

describe('MeetingsPage', () => {
  it('renders rows per tab with counts', async () => {
    mockApi(basic);
    renderPage();
    expect(await screen.findByText('We shipped it.')).toBeInTheDocument();
    expect(screen.getByText('Unfiled')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Weekly sync/ })).toHaveAttribute(
      'href',
      '/meetings/r1',
    );
    expect(screen.getByRole('tab', { name: 'Ready 1' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: 'Processing 1' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Incomplete 1' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'Processing 1' }));
    expect(await screen.findByText('Working on it: Transcribing')).toBeInTheDocument();
    expect(screen.getByTestId('where')).toHaveTextContent('tab=processing');

    fireEvent.click(screen.getByRole('tab', { name: 'Incomplete 1' }));
    expect(await screen.findByText('Lost audio.')).toBeInTheDocument();
    expect(screen.getByText('Incomplete', { selector: 'span' })).toBeInTheDocument();
  });

  it('debounces search and passes q', async () => {
    const spy = mockApi(basic);
    renderPage();
    await screen.findByText('We shipped it.');
    fireEvent.change(screen.getByLabelText('Search meetings'), { target: { value: 'sync' } });
    expect(urlsOf(spy).some((u) => u.searchParams.get('q') === 'sync')).toBe(false);
    await waitFor(() =>
      expect(urlsOf(spy).some((u) => u.searchParams.get('q') === 'sync')).toBe(true),
    );
    expect(urlsOf(spy).filter((u) => u.searchParams.get('q')).length).toBe(1);
  });

  it('shows the empty state when there are no meetings, and a per-tab empty text otherwise', async () => {
    mockApi({ counts: { ready: 0, processing: 0, incomplete: 0 }, byStatus: {} });
    renderPage();
    expect(await screen.findByText('No meetings yet')).toBeInTheDocument();
    expect(
      screen.getByText('Recorded meetings appear here with a recap, follow-ups and a transcript.'),
    ).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: 'Upload' })[1]);
    expect(screen.getByRole('dialog', { name: 'Upload a recording' })).toBeInTheDocument();
  });

  it('shows "Nothing in this view." for an empty tab', async () => {
    mockApi({ counts: { ready: 1, processing: 0, incomplete: 0 }, byStatus: { ready: [ready1] } });
    renderPage('/meetings?tab=incomplete');
    expect(await screen.findByText('Nothing in this view.')).toBeInTheDocument();
  });

  it('shows the API error with a Retry button', async () => {
    let fail = true;
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        fail
          ? new Response(JSON.stringify({ error: { code: 'internal_error', message: 'Boom.' } }), {
              status: 500,
            })
          : new Response(JSON.stringify({ items: [ready1], next_cursor: null, meta: { counts } }), {
              status: 200,
            }),
      ),
    );
    renderPage();
    expect(await screen.findByText('Boom.')).toBeInTheDocument();
    fail = false;
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('We shipped it.')).toBeInTheDocument();
  });

  it('validates the file, uploads with language and title, then switches to Processing', async () => {
    const created = meeting({
      id: 'n1',
      title: 'standup',
      status: 'processing',
      stage: 'uploading',
    });
    vi.mocked(uploadMeeting).mockResolvedValue(created);
    mockApi({
      counts,
      byStatus: { ready: [ready1], processing: [proc1], incomplete: [inc1] },
    });
    renderPage('/meetings?upload=1');
    const dialog = await screen.findByRole('dialog', { name: 'Upload a recording' });
    const start = within(dialog).getByRole('button', { name: 'Start processing' });
    expect(start).toBeDisabled();

    const input = within(dialog).getByLabelText('Recording file');
    fireEvent.change(input, { target: { files: [new File(['x'], 'notes.txt')] } });
    expect(within(dialog).getByRole('alert')).toHaveTextContent('Unsupported file type');
    expect(start).toBeDisabled();

    fireEvent.change(input, { target: { files: [new File(['abc'], 'standup.mp3')] } });
    expect(within(dialog).queryByRole('alert')).not.toBeInTheDocument();
    expect(within(dialog).getByLabelText('Title')).toHaveValue('standup');
    expect(within(dialog).getByText('standup.mp3')).toBeInTheDocument();
    fireEvent.change(within(dialog).getByLabelText('Language'), { target: { value: 'vi' } });
    expect(start).toBeEnabled();
    fireEvent.click(start);

    await waitFor(() => expect(uploadMeeting).toHaveBeenCalledTimes(1));
    const [arg] = vi.mocked(uploadMeeting).mock.calls[0];
    expect(arg.language).toBe('vi');
    expect(arg.title).toBe('standup');
    expect(arg.file.name).toBe('standup.mp3');

    expect(await screen.findByText('Upload started. It shows as Processing.')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Processing/ })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(await screen.findByText('standup')).toBeInTheDocument();
    expect(screen.getByText('Design review')).toBeInTheDocument();
  });

  it('rejects a file over 500 MB', async () => {
    mockApi(basic);
    renderPage('/meetings?upload=1');
    const big = new File(['x'], 'big.mp4');
    Object.defineProperty(big, 'size', { value: 501 * 1024 * 1024 });
    fireEvent.change(await screen.findByLabelText('Recording file'), { target: { files: [big] } });
    expect(screen.getByRole('alert')).toHaveTextContent('File is too large');
  });

  it('updates the stage from SSE and removes a meeting that becomes ready', async () => {
    const spy = mockApi(basic);
    renderPage('/meetings?tab=processing');
    expect(await screen.findByText('Working on it: Transcribing')).toBeInTheDocument();
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const source = FakeEventSource.instances[0];
    expect(source.url).toBe('/api/v1/meetings/p1/events');
    expect(source.withCredentials).toBe(true);

    source.emit('stage', { stage: 'summarizing' });
    expect(await screen.findByText('Working on it: Summarizing')).toBeInTheDocument();

    spy.mockClear();
    source.emit('status', { status: 'ready', error: null });
    await waitFor(() => expect(screen.queryByText('Design review')).not.toBeInTheDocument());
    expect(await screen.findByText('Design review is ready')).toBeInTheDocument();
    expect(source.closed).toBe(true);
    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(screen.getByText('Nothing in this view.')).toBeInTheDocument();
  });

  it('closes event streams when leaving the Processing tab', async () => {
    mockApi(basic);
    renderPage('/meetings?tab=processing');
    await screen.findByText('Design review');
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    fireEvent.click(screen.getByRole('tab', { name: /Ready/ }));
    await waitFor(() => expect(FakeEventSource.instances[0].closed).toBe(true));
  });

  it('appends more rows with Load more', async () => {
    const ready2 = meeting({ id: 'r2', title: 'Retro', summary_preview: 'Went fine.' });
    const spy = mockApi({
      counts: { ready: 2, processing: 0, incomplete: 0 },
      byStatus: { ready: [ready1], 'ready:c1': [ready2] },
      next: 'c1',
    });
    renderPage();
    await screen.findByText('Weekly sync');
    expect(screen.queryByText('Retro')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Load more' }));
    expect(await screen.findByText('Retro')).toBeInTheDocument();
    expect(screen.getByText('Weekly sync')).toBeInTheDocument();
    expect(urlsOf(spy).some((u) => u.searchParams.get('cursor') === 'c1')).toBe(true);
    expect(screen.queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument();
  });
});
