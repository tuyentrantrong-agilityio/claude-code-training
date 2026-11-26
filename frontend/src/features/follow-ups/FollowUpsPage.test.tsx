import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ToastProvider } from '../../components/Toast';
import { setCsrfToken } from '../../lib/api';
import { mockFetch } from '../../test-helpers';
import FollowUpsPage from './FollowUpsPage';

const mine = {
  id: 'f1',
  text: 'Send the launch plan',
  owner_name: 'Alex Rivera',
  owner_user_id: 'u1',
  at_ms: 65000,
  state: 'open',
  meeting_id: 'm1',
  meeting_title: 'Weekly sync',
};
const theirs = {
  ...mine,
  id: 'f2',
  text: 'Book the venue',
  owner_name: 'Sam Lee',
  owner_user_id: 'u2',
  at_ms: null,
};

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <FollowUpsPage />
      </ToastProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => setCsrfToken('csrf-123'));
afterEach(() => {
  vi.unstubAllGlobals();
  setCsrfToken(null);
});

describe('FollowUpsPage', () => {
  it('lists my follow-ups and switches to everyone', async () => {
    const spy = mockFetch({
      'GET /follow-ups?owner=me&state=open': { body: { items: [mine] } },
      'GET /follow-ups?owner=all&state=open': { body: { items: [mine, theirs] } },
    });
    renderPage();
    expect(screen.getByRole('heading', { level: 1, name: 'Follow-ups' })).toBeInTheDocument();
    expect(screen.getByText('What needs doing, and what Recapz suggests')).toBeInTheDocument();
    expect(await screen.findByText('Send the launch plan')).toBeInTheDocument();
    expect(screen.getByText('Alex Rivera . Weekly sync')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Jump to 01:05' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Mine' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.queryByText('Book the venue')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Everyone' }));
    expect(await screen.findByText('Book the venue')).toBeInTheDocument();
    expect(screen.getByText('Sam Lee . Weekly sync')).toBeInTheDocument();
    expect(spy.mock.calls.map(([u]) => String(u))).toContain(
      '/api/v1/follow-ups?owner=all&state=open',
    );
  });

  it('toggles a follow-up with a PATCH and refreshes the badge count', async () => {
    const spy = mockFetch({
      'GET /follow-ups?owner=me&state=open': { body: { items: [mine] } },
      'PATCH /follow-ups/f1': { body: {} },
    });
    renderPage();
    const box = await screen.findByRole('checkbox', { name: /Send the launch plan/ });
    fireEvent.click(box);
    expect(box).toBeChecked();
    await waitFor(() =>
      expect(
        spy.mock.calls.some(
          ([u, i]) => String(u) === '/api/v1/follow-ups/f1' && i?.method === 'PATCH',
        ),
      ).toBe(true),
    );
    const call = spy.mock.calls.find(([, i]) => i?.method === 'PATCH');
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ state: 'done' });
    expect((call?.[1]?.headers as Record<string, string>)['X-CSRF-Token']).toBe('csrf-123');
  });

  it('rolls back when the PATCH fails', async () => {
    mockFetch({
      'GET /follow-ups?owner=me&state=open': { body: { items: [mine] } },
      'PATCH /follow-ups/f1': { status: 500, body: { error: { code: 'x', message: 'Nope' } } },
    });
    renderPage();
    const box = await screen.findByRole('checkbox', { name: /Send the launch plan/ });
    fireEvent.click(box);
    expect(await screen.findByText('Nope')).toBeInTheDocument();
    expect(box).not.toBeChecked();
  });

  it('shows the empty states', async () => {
    mockFetch({ 'GET /follow-ups?owner=me&state=open': { body: { items: [] } } });
    renderPage();
    expect(await screen.findByRole('heading', { name: 'Nothing to do' })).toBeInTheDocument();
    expect(screen.getByText('Follow-ups from your meetings land here.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab', { name: 'Suggested' }));
    expect(screen.getByRole('heading', { name: 'All reviewed' })).toBeInTheDocument();
    expect(screen.getByText('New suggestions appear after your next meeting.')).toBeInTheDocument();
  });
});
