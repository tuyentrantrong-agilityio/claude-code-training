import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { ToastProvider } from '../../components/Toast';
import { setCsrfToken } from '../../lib/api';
import { mockFetch, type Routes as FetchRoutes } from '../../test-helpers';
import MeetingPage from './MeetingPage';
import type { MeetingDetail, Person, Recap, Segment } from './report-api';

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  closed = false;
  listeners: Record<string, ((e: { data: string }) => void)[]> = {};
  constructor(url: string) {
    this.url = url;
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

type TimedMedia = HTMLMediaElement & { _t?: number };
const play = vi.fn(() => Promise.resolve());
const pause = vi.fn();

beforeAll(() => {
  Object.defineProperty(HTMLMediaElement.prototype, 'currentTime', {
    configurable: true,
    get(this: TimedMedia) {
      return this._t ?? 0;
    },
    set(this: TimedMedia, v: number) {
      this._t = v;
    },
  });
  Object.defineProperty(HTMLMediaElement.prototype, 'play', { configurable: true, value: play });
  Object.defineProperty(HTMLMediaElement.prototype, 'pause', { configurable: true, value: pause });
});

beforeEach(() => {
  FakeEventSource.instances = [];
  play.mockClear();
  pause.mockClear();
  vi.stubGlobal('EventSource', FakeEventSource);
  setCsrfToken('csrf-123');
});

afterEach(() => {
  vi.unstubAllGlobals();
  setCsrfToken(null);
});

const meeting: MeetingDetail = {
  id: 'm1',
  title: 'Weekly sync',
  status: 'ready',
  stage: null,
  error: null,
  source: 'upload',
  platform: 'zoom',
  language: 'en',
  started_at: '2026-11-19T12:00:00Z',
  duration_ms: 45 * 60000,
  participants: [
    { id: 'p1', display_name: 'Alex Rivera' },
    { id: 'p2', display_name: 'Sam Lee' },
  ],
};

const recap: Recap = {
  summary: 'We agreed to ship on Friday.',
  summary_edited_at: null,
  follow_ups: [
    {
      id: 'f1',
      text: 'Send the launch plan',
      owner_name: 'Alex Rivera',
      owner_user_id: 'u1',
      at_ms: 65000,
      state: 'open',
    },
  ],
  key_points: [{ id: 'k1', title: 'Launch date', text: 'Friday is the target.', at_ms: 30000 }],
  chapters: [
    { id: 'c1', title: 'Kickoff', at_ms: 0 },
    { id: 'c2', title: 'Budget talk', at_ms: 600000 },
  ],
  highlights: [{ id: 'h1', text: 'We cannot slip again', at_ms: 120000 }],
  questions: [{ id: 'q1', text: 'Who owns QA?', at_ms: 150000 }],
};

const segments: Segment[] = [
  {
    id: 's1',
    seq: 1,
    start_ms: 0,
    end_ms: 10000,
    participant_id: 'p1',
    speaker: 'Alex Rivera',
    text: 'Welcome to the budget review.',
  },
  {
    id: 's2',
    seq: 2,
    start_ms: 10000,
    end_ms: 20000,
    participant_id: 'p2',
    speaker: 'Sam Lee',
    text: 'The launch is on Friday.',
  },
];

const people: Person[] = [
  {
    participant_id: 'p1',
    display_name: 'Alex Rivera',
    speaker_label: 'S1',
    talk_ms: 1,
    share: 0.6,
  },
  { participant_id: 'p2', display_name: 'Sam Lee', speaker_label: 'S2', talk_ms: 1, share: 0.4 },
];

const readyRoutes: FetchRoutes = {
  'GET /meetings/m1': { body: meeting },
  'GET /meetings/m1/recap': { body: recap },
  'GET /meetings/m1/transcript': { body: { segments } },
  'GET /meetings/m1/people': { body: { people } },
};

function Where() {
  const loc = useLocation();
  return <output data-testid="where">{loc.pathname + loc.search}</output>;
}

function renderAt(path = '/meetings/m1') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ToastProvider>
        <Routes>
          <Route path="/meetings/:id" element={<MeetingPage />} />
          <Route path="*" element={null} />
        </Routes>
        <Where />
      </ToastProvider>
    </MemoryRouter>,
  );
}

function audio(): TimedMedia {
  return document.querySelector('audio') as TimedMedia;
}

function callsTo(spy: ReturnType<typeof mockFetch>, method: string, path: string) {
  return spy.mock.calls.filter(
    ([input, init]) => String(input) === `/api/v1${path}` && (init?.method ?? 'GET') === method,
  );
}

describe('MeetingPage report', () => {
  it('renders the header, summary, follow-ups, key points and chapters', async () => {
    mockFetch(readyRoutes);
    renderAt();
    expect(await screen.findByText('We agreed to ship on Friday.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'Weekly sync' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Meetings' })).toHaveAttribute('href', '/meetings');
    expect(screen.getByText(/ \. Zoom \. 45 min$/)).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /Send the launch plan/ })).not.toBeChecked();
    expect(screen.getByText('Launch date')).toBeInTheDocument();
    expect(screen.getByText('Friday is the target.')).toBeInTheDocument();
    expect(screen.getByText('We cannot slip again')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Who owns QA?' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Kickoff/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Budget talk/ })).toBeInTheDocument();
    expect(screen.getAllByTestId('chapter-mark')).toHaveLength(2);
    expect(audio()).toHaveAttribute('src', '/api/v1/meetings/m1/audio');
    expect(screen.getByRole('button', { name: 'Share' })).toBeDisabled();
  });

  it('shows None found for empty sections', async () => {
    mockFetch({
      ...readyRoutes,
      'GET /meetings/m1/recap': {
        body: {
          ...recap,
          summary: null,
          follow_ups: [],
          key_points: [],
          chapters: [],
          highlights: [],
          questions: [],
        },
      },
    });
    renderAt();
    await screen.findByRole('heading', { name: 'Summary' });
    expect(screen.getAllByText('None found.').length).toBeGreaterThanOrEqual(6);
  });

  it('lists exports and disabled push actions in the More menu', async () => {
    mockFetch(readyRoutes);
    renderAt();
    fireEvent.click(await screen.findByRole('button', { name: 'More' }));
    expect(screen.getByRole('menuitem', { name: 'Download transcript' })).toHaveAttribute(
      'href',
      '/api/v1/meetings/m1/export/transcript.txt',
    );
    expect(screen.getByRole('menuitem', { name: 'Download recap' })).toHaveAttribute(
      'href',
      '/api/v1/meetings/m1/export/recap.md',
    );
    for (const name of ['Push to Slack', 'Push to Notion', 'Send to webhook']) {
      const item = screen.getByRole('menuitem', { name });
      expect(item).toBeDisabled();
      expect(item).toHaveAttribute('title', 'Comes later');
    }
  });

  it('renames the title inline with Enter and cancels with Escape', async () => {
    const spy = mockFetch({ ...readyRoutes, 'PATCH /meetings/m1': { body: {} } });
    renderAt();
    fireEvent.click(await screen.findByRole('button', { name: 'Weekly sync' }));
    let input = screen.getByRole('textbox', { name: 'Meeting title' });
    fireEvent.change(input, { target: { value: 'Ignored' } });
    fireEvent.keyDown(input, { key: 'Escape' });
    expect(screen.getByRole('heading', { level: 1, name: 'Weekly sync' })).toBeInTheDocument();
    expect(callsTo(spy, 'PATCH', '/meetings/m1')).toHaveLength(0);

    fireEvent.click(screen.getByRole('button', { name: 'Weekly sync' }));
    input = screen.getByRole('textbox', { name: 'Meeting title' });
    fireEvent.change(input, { target: { value: 'Planning' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(await screen.findByRole('heading', { level: 1, name: 'Planning' })).toBeInTheDocument();
    const [, init] = callsTo(spy, 'PATCH', '/meetings/m1')[0];
    expect(JSON.parse(String(init?.body))).toEqual({ title: 'Planning' });
    expect((init?.headers as Record<string, string>)['X-CSRF-Token']).toBe('csrf-123');
  });

  it('toggles a follow-up with a PATCH and CSRF token', async () => {
    const spy = mockFetch({ ...readyRoutes, 'PATCH /follow-ups/f1': { body: {} } });
    renderAt();
    const box = await screen.findByRole('checkbox', { name: /Send the launch plan/ });
    fireEvent.click(box);
    expect(box).toBeChecked();
    await waitFor(() => expect(callsTo(spy, 'PATCH', '/follow-ups/f1')).toHaveLength(1));
    const [, init] = callsTo(spy, 'PATCH', '/follow-ups/f1')[0];
    expect(JSON.parse(String(init?.body))).toEqual({ state: 'done' });
    expect((init?.headers as Record<string, string>)['X-CSRF-Token']).toBe('csrf-123');
  });

  it('rolls the follow-up back when the PATCH fails', async () => {
    mockFetch({
      ...readyRoutes,
      'PATCH /follow-ups/f1': {
        status: 500,
        body: { error: { code: 'boom', message: 'Could not save' } },
      },
    });
    renderAt();
    const box = await screen.findByRole('checkbox', { name: /Send the launch plan/ });
    fireEvent.click(box);
    expect(await screen.findByText('Could not save')).toBeInTheDocument();
    expect(box).not.toBeChecked();
  });

  it('edits and saves the summary, and cancel keeps the old text', async () => {
    const spy = mockFetch({ ...readyRoutes, 'PATCH /meetings/m1': { body: {} } });
    renderAt();
    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Summary text' }), {
      target: { value: 'Draft' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.getByText('We agreed to ship on Friday.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Summary text' }), {
      target: { value: 'New summary' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() =>
      expect(screen.queryByRole('textbox', { name: 'Summary text' })).not.toBeInTheDocument(),
    );
    expect(screen.getByText('New summary')).toBeInTheDocument();
    const [, init] = callsTo(spy, 'PATCH', '/meetings/m1')[0];
    expect(JSON.parse(String(init?.body))).toEqual({ summary: 'New summary' });
    expect((init?.headers as Record<string, string>)['X-CSRF-Token']).toBe('csrf-123');
  });

  it('copies the summary and shows a toast', async () => {
    mockFetch(readyRoutes);
    const writeText = vi.fn(() => Promise.resolve());
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } });
    renderAt();
    fireEvent.click(await screen.findByRole('button', { name: 'Copy' }));
    expect(await screen.findByText('Summary copied')).toBeInTheDocument();
    expect(writeText).toHaveBeenCalledWith('We agreed to ship on Friday.');
  });

  it('opens Ask with a raised question and with the side panel prompts', async () => {
    mockFetch(readyRoutes);
    renderAt();
    fireEvent.click(await screen.findByRole('button', { name: 'Who owns QA?' }));
    expect(screen.getByTestId('where')).toHaveTextContent('/ask?q=Who+owns+QA%3F');
  });

  it('submits a question from the Ask box with the meeting id', async () => {
    mockFetch(readyRoutes);
    renderAt();
    await screen.findByText('We agreed to ship on Friday.');
    expect(screen.getByRole('button', { name: 'Summarize this meeting' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'What are the follow-ups?' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Who owns the next steps?' })).toBeInTheDocument();
    fireEvent.change(screen.getByRole('textbox', { name: 'Ask a question' }), {
      target: { value: 'What was decided?' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));
    expect(screen.getByTestId('where')).toHaveTextContent('/ask?q=What+was+decided%3F&meeting=m1');
  });

  it('keeps the tab in the URL', async () => {
    mockFetch(readyRoutes);
    renderAt('/meetings/m1?tab=people');
    expect(await screen.findByText('Who spoke')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'People' })).toHaveAttribute('aria-selected', 'true');
    fireEvent.click(screen.getByRole('tab', { name: 'Transcript' }));
    expect(screen.getByTestId('where')).toHaveTextContent('tab=transcript');
  });
});

describe('MeetingPage transcript and player', () => {
  it('filters and highlights search matches', async () => {
    mockFetch(readyRoutes);
    renderAt('/meetings/m1?tab=transcript');
    expect(await screen.findByRole('button', { name: /Welcome to/ })).toBeInTheDocument();
    fireEvent.change(screen.getByRole('searchbox', { name: 'Search transcript' }), {
      target: { value: 'BUDGET' },
    });
    const marks = document.querySelectorAll('mark');
    expect(marks).toHaveLength(1);
    expect(marks[0]).toHaveTextContent('budget');
    expect(screen.queryByText(/The launch is on Friday/)).not.toBeInTheDocument();
  });

  it('seeks the player when a line is clicked and marks the current line', async () => {
    mockFetch(readyRoutes);
    renderAt('/meetings/m1?tab=transcript');
    const line = await screen.findByRole('button', { name: /The launch is on Friday/ });
    fireEvent.click(line);
    expect(audio().currentTime).toBe(10);

    fireEvent.timeUpdate(audio());
    await waitFor(() => expect(line).toHaveAttribute('aria-current', 'true'));
    expect(screen.getByRole('button', { name: /Welcome to the budget/ })).not.toHaveAttribute(
      'aria-current',
    );
    // The big avatar follows the current speaker.
    expect(screen.getByText('Sam Lee', { selector: 'small' })).toBeInTheDocument();
    expect(screen.getByText('00:10 / 45:00')).toBeInTheDocument();
  });

  it('seeks from ?t= on load and when it changes', async () => {
    mockFetch(readyRoutes);
    renderAt('/meetings/m1?t=75');
    await screen.findByText('We agreed to ship on Friday.');
    expect(audio().currentTime).toBe(75);

    fireEvent.click(screen.getByRole('button', { name: 'Jump to 02:00' }));
    await waitFor(() => expect(audio().currentTime).toBe(120));
  });

  it('seeks and plays from a chapter, and drives play, pause, -15s and speed', async () => {
    mockFetch(readyRoutes);
    renderAt();
    fireEvent.click(await screen.findByRole('button', { name: /Budget talk/ }));
    expect(audio().currentTime).toBe(600);
    expect(play).toHaveBeenCalled();

    fireEvent.timeUpdate(audio());
    fireEvent.click(screen.getByRole('button', { name: '-15s' }));
    expect(audio().currentTime).toBe(585);

    fireEvent.click(screen.getByRole('button', { name: 'Play' }));
    expect(play).toHaveBeenCalledTimes(2);
    fireEvent.play(audio());
    fireEvent.click(await screen.findByRole('button', { name: 'Pause' }));
    expect(pause).toHaveBeenCalled();

    fireEvent.change(screen.getByRole('combobox', { name: 'Playback speed' }), {
      target: { value: '1.5' },
    });
    expect(audio().playbackRate).toBe(1.5);
  });

  it('seeks when the seek bar is clicked', async () => {
    mockFetch(readyRoutes);
    renderAt();
    const bar = await screen.findByRole('slider', { name: 'Seek' });
    bar.getBoundingClientRect = () =>
      ({ left: 0, width: 200, top: 0, height: 10, right: 200, bottom: 10 }) as DOMRect;
    fireEvent.click(bar, { clientX: 100 });
    expect(audio().currentTime).toBe(1350);
  });
});

describe('MeetingPage people', () => {
  it('shows talk share and renames a person, then refreshes the transcript', async () => {
    const spy = mockFetch({
      ...readyRoutes,
      'PATCH /meetings/m1/participants/p2': { body: {} },
    });
    renderAt('/meetings/m1?tab=people');
    expect(await screen.findByText('60%')).toBeInTheDocument();
    expect(screen.getByText('40%')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Sam Lee' }));
    const input = screen.getByRole('textbox', { name: 'Participant name' });
    fireEvent.change(input, { target: { value: 'Samantha Lee' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    await waitFor(() =>
      expect(callsTo(spy, 'PATCH', '/meetings/m1/participants/p2')).toHaveLength(1),
    );
    const [, init] = callsTo(spy, 'PATCH', '/meetings/m1/participants/p2')[0];
    expect(JSON.parse(String(init?.body))).toEqual({ display_name: 'Samantha Lee' });
    expect((init?.headers as Record<string, string>)['X-CSRF-Token']).toBe('csrf-123');
    await waitFor(() => expect(callsTo(spy, 'GET', '/meetings/m1/transcript')).toHaveLength(2));
    await waitFor(() => expect(callsTo(spy, 'GET', '/meetings/m1/people')).toHaveLength(2));
  });
});

describe('MeetingPage other states', () => {
  it('shows not found with a link back', async () => {
    mockFetch({
      'GET /meetings/m1': {
        status: 404,
        body: { error: { code: 'meeting_not_found', message: 'Not found' } },
      },
    });
    renderAt();
    expect(await screen.findByRole('heading', { name: 'Meeting not found' })).toBeInTheDocument();
    expect(screen.getByText('It may have been deleted.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to Meetings' })).toHaveAttribute(
      'href',
      '/meetings',
    );
  });

  it('shows a loading skeleton first', () => {
    mockFetch(readyRoutes);
    renderAt();
    expect(screen.getByRole('status', { name: 'Loading meeting' })).toBeInTheDocument();
  });

  it('shows the stage while processing and loads the report after the ready event', async () => {
    let calls = 0;
    mockFetch({
      ...readyRoutes,
      'GET /meetings/m1': () => {
        calls += 1;
        return {
          body: calls === 1 ? { ...meeting, status: 'processing', stage: 'transcribing' } : meeting,
        };
      },
    });
    renderAt();
    expect(await screen.findByText('Working on it: Transcribing')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Processing progress' })).toHaveAttribute(
      'aria-valuenow',
      '50',
    );
    expect(screen.queryByRole('button', { name: 'More' })).not.toBeInTheDocument();
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(FakeEventSource.instances[0].url).toBe('/api/v1/meetings/m1/events');

    act(() => FakeEventSource.instances[0].emit('stage', { stage: 'summarizing' }));
    expect(await screen.findByText('Working on it: Summarizing')).toBeInTheDocument();

    act(() => FakeEventSource.instances[0].emit('status', { status: 'ready' }));
    expect(await screen.findByText('We agreed to ship on Friday.')).toBeInTheDocument();
    expect(screen.queryByText(/Working on it/)).not.toBeInTheDocument();
  });

  it('retries an incomplete meeting and then shows processing', async () => {
    const spy = mockFetch({
      'GET /meetings/m1': {
        body: { ...meeting, status: 'incomplete', error: 'Connection lost after 03:12.' },
      },
      'POST /meetings/m1/retry': { status: 202, body: {} },
    });
    renderAt();
    expect(await screen.findByText('Connection lost after 03:12.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Process what was saved' }));
    expect(await screen.findByText(/Working on it/)).toBeInTheDocument();
    const [, init] = callsTo(spy, 'POST', '/meetings/m1/retry')[0];
    expect((init?.headers as Record<string, string>)['X-CSRF-Token']).toBe('csrf-123');
  });

  it('deletes an incomplete meeting after confirming, then goes to the list', async () => {
    const spy = mockFetch({
      'GET /meetings/m1': { body: { ...meeting, status: 'incomplete', error: 'Lost audio.' } },
      'DELETE /meetings/m1': { status: 204 },
    });
    renderAt();
    fireEvent.click(await screen.findByRole('button', { name: 'Delete' }));
    expect(callsTo(spy, 'DELETE', '/meetings/m1')).toHaveLength(0);
    const dialog = screen.getByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent(/^\/meetings$/));
    expect(callsTo(spy, 'DELETE', '/meetings/m1')).toHaveLength(1);
    expect(await screen.findByText('Meeting deleted')).toBeInTheDocument();
  });
});
