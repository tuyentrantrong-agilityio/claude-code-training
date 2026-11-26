import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '../../App';
import { mockFetch, ownerMe } from '../../test-helpers';

afterEach(() => {
  vi.unstubAllGlobals();
});

const members = [
  { user_id: 'u1', email: 'alex@example.com', name: 'Alex Rivera', role: 'owner' },
  { user_id: 'u2', email: 'sam@example.com', name: 'Sam Lee', role: 'member' },
];

function renderAdmin() {
  return render(
    <MemoryRouter initialEntries={['/admin']}>
      <App />
    </MemoryRouter>,
  );
}

describe('AdminPage', () => {
  it('lists members and pending invites', async () => {
    mockFetch({
      'GET /me': { body: ownerMe },
      'GET /admin/members': { body: members },
      'GET /admin/invites': {
        body: [
          {
            id: 'i1',
            email: 'new@example.com',
            role: 'member',
            expires_at: '2030-01-01T00:00:00Z',
          },
        ],
      },
    });
    renderAdmin();
    expect(await screen.findByText('sam@example.com')).toBeInTheDocument();
    expect(screen.getByText('new@example.com')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Revoke' })).toBeInTheDocument();
    expect(screen.getByLabelText('Role for sam@example.com')).toHaveValue('member');
  });

  it('posts an invite with the CSRF header and toasts the result', async () => {
    const spy = mockFetch({
      'GET /me': { body: ownerMe },
      'GET /admin/members': { body: members },
      'GET /admin/invites': { body: [] },
      'POST /admin/invites': {
        status: 201,
        body: {
          id: 'i2',
          email: 'new@example.com',
          role: 'owner',
          expires_at: '2030-01-01T00:00:00Z',
        },
      },
    });
    renderAdmin();
    await screen.findByText('sam@example.com');
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'new@example.com' } });
    fireEvent.change(screen.getByLabelText('Role'), { target: { value: 'owner' } });
    fireEvent.click(screen.getByRole('button', { name: 'Invite' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Invited new@example.com');
    const call = spy.mock.calls.find(
      ([url, init]) => url === '/api/v1/admin/invites' && init?.method === 'POST',
    );
    expect(call).toBeDefined();
    const init = call?.[1] as RequestInit;
    expect((init.headers as Record<string, string>)['X-CSRF-Token']).toBe('csrf-123');
    expect(JSON.parse(String(init.body))).toEqual({ email: 'new@example.com', role: 'owner' });
  });

  it('shows the API error message', async () => {
    mockFetch({
      'GET /me': { body: ownerMe },
      'GET /admin/members': { body: members },
      'GET /admin/invites': { body: [] },
      'POST /admin/invites': {
        status: 409,
        body: {
          error: {
            code: 'invite_exists',
            message: 'A pending invite already exists for that email',
            details: {},
          },
        },
      },
    });
    renderAdmin();
    await screen.findByText('sam@example.com');
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'dup@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: 'Invite' }));
    expect(await screen.findByRole('status')).toHaveTextContent(
      'A pending invite already exists for that email',
    );
  });

  it('gates the page for members', async () => {
    mockFetch({ 'GET /me': { body: { ...ownerMe, role: 'member' } } });
    renderAdmin();
    expect(await screen.findByText('Only owners can open this page')).toBeInTheDocument();
  });
});
