import { useEffect, useRef, useState, type ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import { Avatar } from '../components/Avatar';
import { Icon, type IconName } from '../components/Icon';
import type { Role } from './useMe';

interface RailProps {
  user: { name: string; email: string };
  org: { name: string };
  role: Role;
  followUpCount?: number;
  canPreview?: boolean;
  onToggleRole: () => void;
  onSignOut?: () => void;
}

const navClass = ({ isActive }: { isActive: boolean }) =>
  `flex h-[38px] w-full items-center gap-2.5 rounded-control px-2.5 no-underline ${
    isActive ? 'bg-accent-soft font-semibold text-accent' : 'font-medium text-ink hover:bg-sunken'
  }`;

function Item({
  to,
  icon,
  label,
  badge = 0,
}: {
  to: string;
  icon: IconName;
  label: string;
  badge?: number;
}) {
  return (
    <NavLink to={to} className={navClass}>
      <Icon name={icon} />
      {label}
      {badge > 0 && (
        <span className="ml-auto inline-flex h-[22px] items-center rounded-full bg-accent-soft px-[9px] text-xs font-semibold text-accent">
          {badge}
        </span>
      )}
    </NavLink>
  );
}

function Heading({ children }: { children: ReactNode }) {
  return (
    <h4 className="mx-2.5 mt-4 mb-1 text-[0.7rem] font-semibold tracking-[0.08em] text-muted uppercase">
      {children}
    </h4>
  );
}

function OrgSwitcher({
  org,
  role,
  canPreview,
  onToggleRole,
  onSignOut,
}: Pick<RailProps, 'org' | 'role' | 'onToggleRole' | 'onSignOut'> & { canPreview: boolean }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const other = role === 'owner' ? 'member' : 'owner';
  const itemClass =
    'flex w-full cursor-pointer items-center gap-2.5 rounded-lg border-0 bg-transparent px-2.5 py-2 text-left font-medium hover:bg-sunken';

  return (
    <div ref={ref} className="relative mb-2.5">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex w-full cursor-pointer items-center gap-2.5 rounded-xl border border-line bg-bg px-2.5 py-2 text-left"
      >
        <Avatar name={org.name} square />
        <span className="flex min-w-0 flex-1 flex-col">
          <b className="truncate text-[0.92rem] leading-tight">{org.name}</b>
          <small className="text-muted">{role === 'owner' ? 'Owner' : 'Member'}</small>
        </span>
        <Icon name="chev" />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute top-[calc(100%+6px)] right-0 left-0 z-30 flex min-w-[210px] flex-col rounded-xl border border-line bg-surface p-1.5 shadow-pop"
        >
          {canPreview && (
            <button
              type="button"
              role="menuitem"
              className={itemClass}
              onClick={() => {
                onToggleRole();
                setOpen(false);
              }}
            >
              <Icon name="shield" />
              Preview as {other}
            </button>
          )}
          <button
            type="button"
            role="menuitem"
            className={itemClass}
            onClick={() => {
              onSignOut?.();
              setOpen(false);
            }}
          >
            <Icon name="out" />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

export function Rail({
  user,
  org,
  role,
  followUpCount = 0,
  canPreview = true,
  onToggleRole,
  onSignOut,
}: RailProps) {
  return (
    <aside className="sticky top-0 flex h-screen flex-col gap-0.5 overflow-x-hidden overflow-y-auto border-r border-line bg-surface px-3 py-3.5 max-[860px]:static max-[860px]:h-auto max-[860px]:border-r-0 max-[860px]:border-b">
      <OrgSwitcher
        org={org}
        role={role}
        canPreview={canPreview}
        onToggleRole={onToggleRole}
        onSignOut={onSignOut}
      />
      <nav aria-label="Main" className="flex flex-1 flex-col gap-0.5">
        <Item to="/home" icon="home" label="Home" />
        <Item to="/meetings" icon="video" label="Meetings" />
        <Item to="/ask" icon="chat" label="Ask" />
        <Item to="/live" icon="globe" label="Interpreter" />
        <Item to="/follow-ups" icon="check" label="Follow-ups" badge={followUpCount} />
        <Item to="/week" icon="sun" label="Your week" />
        <Heading>Workspace</Heading>
        <Item to="/folders" icon="folder" label="Folders" />
        <Item to="/calendar" icon="cal" label="Calendar" />
        <Item to="/connections" icon="plug" label="Connections" />
        <div className="flex-1" />
        <Item to="/desktop" icon="screen" label="Desktop app" />
        {role === 'owner' && <Item to="/admin" icon="shield" label="Admin" />}
      </nav>
      <div className="flex items-center gap-2.5 p-2.5">
        <Avatar name={user.name} />
        <div className="flex min-w-0 flex-col">
          <b className="truncate leading-tight">{user.name}</b>
          <small className="truncate text-muted">{user.email}</small>
        </div>
      </div>
    </aside>
  );
}
