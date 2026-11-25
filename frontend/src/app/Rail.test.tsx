import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Rail } from './Rail';
import type { Role } from './useMe';

function renderRail(role: Role, followUpCount = 0, path = '/home') {
  const onToggleRole = vi.fn();
  const onSignOut = vi.fn();
  render(
    <MemoryRouter initialEntries={[path]}>
      <Rail
        user={{ name: 'Alex Rivera', email: 'alex@example.com' }}
        org={{ name: 'Northwind Studio' }}
        role={role}
        followUpCount={followUpCount}
        onToggleRole={onToggleRole}
        onSignOut={onSignOut}
      />
    </MemoryRouter>,
  );
  return { onToggleRole, onSignOut };
}

const items = [
  'Home',
  'Meetings',
  'Ask',
  'Interpreter',
  'Follow-ups',
  'Your week',
  'Folders',
  'Calendar',
  'Connections',
  'Desktop app',
];

describe('Rail', () => {
  it('renders all nav items inside a nav landmark, plus Admin for owners', () => {
    renderRail('owner');
    const nav = screen.getByRole('navigation', { name: 'Main' });
    for (const name of [...items, 'Admin']) {
      expect(screen.getByRole('link', { name })).toBeInTheDocument();
    }
    expect(nav.querySelectorAll('a')).toHaveLength(11);
    expect(screen.getByText('Workspace')).toBeInTheDocument();
    expect(screen.getByText('Owner')).toBeInTheDocument();
  });

  it('hides Admin for members', () => {
    renderRail('member');
    expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument();
    expect(screen.getByText('Member')).toBeInTheDocument();
  });

  it('marks the active link with aria-current', () => {
    renderRail('owner', 0, '/meetings/m1');
    expect(screen.getByRole('link', { name: 'Meetings' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'Home' })).not.toHaveAttribute('aria-current');
  });

  it('shows the Follow-ups badge only when the count is above 0', () => {
    renderRail('owner', 3);
    expect(screen.getByRole('link', { name: /Follow-ups/ })).toHaveTextContent('Follow-ups3');
  });

  it('shows no badge when the count is 0', () => {
    renderRail('owner', 0);
    const link = screen.getByRole('link', { name: 'Follow-ups' });
    expect(link.textContent).toBe('Follow-ups');
  });

  it('hides the role preview item when previewing is not allowed', () => {
    render(
      <MemoryRouter>
        <Rail
          user={{ name: 'Sam', email: 'sam@example.com' }}
          org={{ name: 'Northwind Studio' }}
          role="member"
          canPreview={false}
          onToggleRole={vi.fn()}
        />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: /Northwind Studio/ }));
    expect(screen.queryByRole('menuitem', { name: /Preview as/ })).not.toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Sign out' })).toBeInTheDocument();
  });

  it('shows the user name and email in the footer', () => {
    renderRail('owner');
    expect(screen.getByText('Alex Rivera')).toBeInTheDocument();
    expect(screen.getByText('alex@example.com')).toBeInTheDocument();
  });

  it('opens the org menu, toggles role preview and signs out', () => {
    const { onToggleRole, onSignOut } = renderRail('owner');
    const trigger = screen.getByRole('button', { name: /Northwind Studio/ });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    fireEvent.click(screen.getByRole('menuitem', { name: /Preview as member/ }));
    expect(onToggleRole).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    fireEvent.click(trigger);
    fireEvent.click(screen.getByRole('menuitem', { name: 'Sign out' }));
    expect(onSignOut).toHaveBeenCalledTimes(1);
  });
});
