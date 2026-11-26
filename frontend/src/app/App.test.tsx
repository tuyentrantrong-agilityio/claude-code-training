import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '../App';
import { mockFetch, ownerMe } from '../test-helpers';

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mockFetch({
    'GET /me': { body: ownerMe },
    'GET /admin/members': { body: [] },
    'GET /admin/invites': { body: [] },
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('follow-ups badge', () => {
  it('shows the open count from the API in the rail', async () => {
    mockFetch({
      'GET /me': { body: ownerMe },
      'GET /follow-ups/count': { body: { open_mine: 4 } },
    });
    renderAt('/home');
    await waitFor(() =>
      expect(screen.getByRole('link', { name: /Follow-ups/ })).toHaveTextContent('Follow-ups4'),
    );
  });

  it('updates the badge after a follow-up changes', async () => {
    let open = 2;
    mockFetch({
      'GET /me': { body: ownerMe },
      'GET /follow-ups/count': () => ({ body: { open_mine: open } }),
      'GET /follow-ups?owner=me&state=open': {
        body: {
          items: [
            {
              id: 'f1',
              text: 'Send the plan',
              owner_name: 'Alex Rivera',
              owner_user_id: 'u1',
              at_ms: null,
              state: 'open',
              meeting_id: 'm1',
              meeting_title: 'Sync',
            },
          ],
        },
      },
      'PATCH /follow-ups/f1': () => {
        open = 1;
        return { body: {} };
      },
    });
    renderAt('/follow-ups');
    await waitFor(() =>
      expect(screen.getByRole('link', { name: /Follow-ups/ })).toHaveTextContent('Follow-ups2'),
    );
    fireEvent.click(await screen.findByRole('checkbox', { name: /Send the plan/ }));
    await waitFor(() =>
      expect(screen.getByRole('link', { name: /Follow-ups/ })).toHaveTextContent('Follow-ups1'),
    );
  });
});

describe('routing', () => {
  it('redirects / to /home', async () => {
    renderAt('/');
    await waitFor(() =>
      expect(screen.getByRole('link', { name: 'Home' })).toHaveAttribute('aria-current', 'page'),
    );
    expect(
      screen.getByRole('heading', { level: 1, name: /^Good (morning|afternoon|evening), Alex$/ }),
    ).toBeInTheDocument();
  });

  it('shows the first-time start cards on Home', async () => {
    renderAt('/home');
    expect(await screen.findByRole('link', { name: /Connect your calendar/ })).toHaveAttribute(
      'href',
      '/connections',
    );
    expect(screen.getByRole('link', { name: /Install the desktop app/ })).toHaveAttribute(
      'href',
      '/desktop',
    );
    expect(screen.getByRole('link', { name: /Upload a recording/ })).toHaveAttribute(
      'href',
      '/meetings?upload=1',
    );
  });

  it('shows NotFound for unknown routes with a link home', async () => {
    renderAt('/nope/at/all');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Page not found' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to Home' })).toHaveAttribute('href', '/home');
  });

  it.each([
    ['/meetings', 'Meetings'],
    ['/ask', 'Ask'],
    ['/live', 'Live interpreter'],
    ['/follow-ups', 'Follow-ups'],
    ['/week', 'Your week'],
    ['/folders', 'Folders'],
    ['/calendar', 'Calendar'],
    ['/connections', 'Connections'],
    ['/desktop', 'Desktop app'],
    ['/admin', 'Admin'],
  ])('renders %s', async (path, title) => {
    renderAt(path);
    expect(await screen.findByRole('heading', { level: 1, name: title })).toBeInTheDocument();
  });

  it('hides Admin after previewing as member and gates the admin route', async () => {
    renderAt('/admin');
    fireEvent.click(await screen.findByRole('button', { name: /Northwind Studio/ }));
    fireEvent.click(screen.getByRole('menuitem', { name: /Preview as member/ }));
    expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument();
    expect(screen.getByText('Only owners can open this page')).toBeInTheDocument();
  });
});
