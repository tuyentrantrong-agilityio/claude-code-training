import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '../../App';
import { mockFetch, ownerMe, signedOut } from '../../test-helpers';

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('sign-in page', () => {
  it('shows the sign-in card and links to Google start', async () => {
    mockFetch(signedOut);
    renderAt('/sign-in');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Sign in to Recapz' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Continue with Google' })).toHaveAttribute(
      'href',
      '/api/v1/auth/google/start',
    );
    expect(screen.queryByText(/This account is not invited/)).not.toBeInTheDocument();
  });

  it('shows the not invited message', async () => {
    mockFetch(signedOut);
    renderAt('/sign-in?error=not_invited');
    expect(await screen.findByText('This account is not invited.')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Ask an admin to invite that exact email address, then try again. No account was created.',
    );
  });

  it('redirects to /home when already signed in', async () => {
    mockFetch({ 'GET /me': { body: ownerMe } });
    renderAt('/sign-in');
    expect(await screen.findByRole('link', { name: 'Home' })).toHaveAttribute(
      'aria-current',
      'page',
    );
  });
});

describe('route guard', () => {
  it('redirects signed-out users to /sign-in', async () => {
    const spy = mockFetch(signedOut);
    renderAt('/meetings');
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Sign in to Recapz' }),
    ).toBeInTheDocument();
    expect(spy).toHaveBeenCalledWith(
      '/api/v1/me',
      expect.objectContaining({ credentials: 'include' }),
    );
  });

  it('signs out through the API with the CSRF header and returns to /sign-in', async () => {
    const spy = mockFetch({
      'GET /me': { body: ownerMe },
      'POST /auth/sign-out': { status: 204 },
    });
    renderAt('/home');
    fireEvent.click(await screen.findByRole('button', { name: /Northwind Studio/ }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Sign out' }));
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Sign in to Recapz' }),
    ).toBeInTheDocument();
    const call = spy.mock.calls.find(([url]) => url === '/api/v1/auth/sign-out');
    expect(call).toBeDefined();
    await waitFor(() => {
      expect((call?.[1]?.headers as Record<string, string>)['X-CSRF-Token']).toBe('csrf-123');
    });
  });
});
