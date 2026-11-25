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
      '/meetings',
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
    ['/meetings/m1', 'Meeting'],
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
