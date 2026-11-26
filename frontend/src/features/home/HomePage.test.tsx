import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { SessionContext, type SessionState } from '../../app/useMe';
import { ToastProvider } from '../../components/Toast';
import { setCsrfToken } from '../../lib/api';
import { mockFetch, ownerMe } from '../../test-helpers';
import HomePage from './HomePage';

const session: SessionState = {
  status: 'signed-in',
  me: ownerMe,
  refresh: async () => undefined,
  signOut: async () => undefined,
};

const follow = (n: number, extra = {}) => ({
  id: `f${n}`,
  text: `Task ${n}`,
  owner_name: 'Alex Rivera',
  owner_user_id: 'u1',
  at_ms: 65000,
  state: 'open',
  meeting_id: 'm1',
  meeting_title: 'Weekly sync',
  ...extra,
});

const meeting = (n: number, extra = {}) => ({
  id: `m${n}`,
  title: `Meeting ${n}`,
  status: 'ready',
  stage: null,
  error: null,
  source: 'upload',
  platform: 'meet',
  language: 'en',
  started_at: '2026-11-20T10:00:00Z',
  duration_ms: 1800000,
  summary_preview: `Summary ${n}`,
  participants: [{ id: 'p1', display_name: 'Sam Lee' }],
  folder: null,
  ...extra,
});

function Where() {
  const loc = useLocation();
  return <div data-testid="where">{loc.pathname + loc.search}</div>;
}

function renderHome() {
  return render(
    <SessionContext.Provider value={session}>
      <MemoryRouter initialEntries={['/home']}>
        <ToastProvider>
          <Routes>
            <Route path="/home" element={<HomePage />} />
            <Route path="*" element={<Where />} />
          </Routes>
        </ToastProvider>
      </MemoryRouter>
    </SessionContext.Provider>,
  );
}

beforeEach(() => setCsrfToken('csrf-123'));
afterEach(() => {
  vi.unstubAllGlobals();
  setCsrfToken(null);
});

describe('HomePage', () => {
  it('shows the start cards when there is no meeting', async () => {
    mockFetch({
      'GET /home': { body: { needs_you: [], recent_meetings: [], has_any_meeting: false } },
    });
    renderHome();
    expect(await screen.findByRole('link', { name: /Upload a recording/ })).toHaveAttribute(
      'href',
      '/meetings?upload=1',
    );
    expect(screen.queryByText('Needs you')).not.toBeInTheDocument();
  });

  it('shows an error with Retry', async () => {
    let fail = true;
    mockFetch({
      'GET /home': () =>
        fail
          ? { status: 500, body: { error: { code: 'x', message: 'Boom' } } }
          : { body: { needs_you: [], recent_meetings: [], has_any_meeting: false } },
    });
    renderHome();
    expect(await screen.findByRole('alert')).toHaveTextContent('Boom');
    fail = false;
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('Nothing here yet')).toBeInTheDocument();
  });

  it('lists needs-you items, recent meetings and the cards', async () => {
    mockFetch({
      'GET /home': {
        body: {
          needs_you: [1, 2, 3, 4, 5].map((n) => follow(n)),
          recent_meetings: [1, 2, 3, 4].map((n) =>
            meeting(n, n === 1 ? { folder: { id: 'fo', name: 'Product' } } : {}),
          ),
          has_any_meeting: true,
        },
      },
    });
    renderHome();
    const needs = await screen.findByRole('region', { name: 'Needs you' });
    expect(within(needs).getAllByRole('checkbox')).toHaveLength(4);
    expect(within(needs).getAllByRole('button', { name: 'Jump to 01:05' })[0]).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'See all follow-ups' })).toHaveAttribute(
      'href',
      '/follow-ups',
    );

    const recent = screen.getByRole('region', { name: 'Recent meetings' });
    expect(within(recent).getAllByRole('link', { name: /Meeting \d/ })).toHaveLength(3);
    expect(within(recent).getByText('Summary 1')).toBeInTheDocument();
    expect(within(recent).getByText('Product')).toBeInTheDocument();
    expect(within(recent).getAllByText('Unfiled')).toHaveLength(2);
    expect(within(recent).getAllByText(/30 min/)).toHaveLength(3);
    expect(screen.getByRole('link', { name: 'All meetings' })).toHaveAttribute('href', '/meetings');

    expect(screen.getByText('Connect your calendar to see upcoming meetings here.')).toBeVisible();
    const connect = screen.getByRole('button', { name: 'Connect calendar' });
    expect(connect).toBeDisabled();
    expect(connect).toHaveAttribute('title', 'Comes later');
    expect(screen.getByRole('link', { name: /Your week at a glance/ })).toHaveAttribute(
      'href',
      '/week',
    );
  });

  it('shows the caught-up text when nothing is open', async () => {
    mockFetch({
      'GET /home': {
        body: { needs_you: [], recent_meetings: [meeting(1)], has_any_meeting: true },
      },
    });
    renderHome();
    expect(await screen.findByText('You are all caught up.')).toBeInTheDocument();
    expect(screen.getByText('Nothing is waiting on you right now.')).toBeInTheDocument();
  });

  it('toggles a follow-up with a PATCH carrying the CSRF token', async () => {
    const spy = mockFetch({
      'GET /home': {
        body: { needs_you: [follow(1)], recent_meetings: [], has_any_meeting: true },
      },
      'PATCH /follow-ups/f1': { body: {} },
    });
    renderHome();
    const box = await screen.findByRole('checkbox', { name: /Task 1/ });
    fireEvent.click(box);
    expect(box).toBeChecked();
    await waitFor(() => {
      const call = spy.mock.calls.find(([, i]) => i?.method === 'PATCH');
      expect(call).toBeTruthy();
      const init = call![1] as RequestInit;
      expect(init.body).toBe(JSON.stringify({ state: 'done' }));
      expect((init.headers as Record<string, string>)['X-CSRF-Token']).toBe('csrf-123');
    });
  });

  it('puts the checkbox back when the PATCH fails', async () => {
    mockFetch({
      'GET /home': {
        body: { needs_you: [follow(1)], recent_meetings: [], has_any_meeting: true },
      },
      'PATCH /follow-ups/f1': { status: 500, body: { error: { code: 'x', message: 'No' } } },
    });
    renderHome();
    const box = await screen.findByRole('checkbox', { name: /Task 1/ });
    fireEvent.click(box);
    await waitFor(() => expect(box).not.toBeChecked());
  });

  it('opens Ask with the question from the Ask bar', async () => {
    mockFetch({
      'GET /home': { body: { needs_you: [], recent_meetings: [], has_any_meeting: false } },
    });
    renderHome();
    const input = screen.getByPlaceholderText(
      'Ask about your meetings. For example: what did we decide about the release?',
    );
    fireEvent.change(input, { target: { value: 'what is next?' } });
    fireEvent.submit(input.closest('form')!);
    expect(await screen.findByTestId('where')).toHaveTextContent('/ask?q=what%20is%20next%3F');
  });
});
