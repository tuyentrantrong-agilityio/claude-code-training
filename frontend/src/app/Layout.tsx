import { NavLink, Outlet } from 'react-router-dom';

const links = [
  { to: '/home', label: 'Home' },
  { to: '/meetings', label: 'Meetings' },
  { to: '/ask', label: 'Ask' },
  { to: '/follow-ups', label: 'Follow-ups' },
];

export default function Layout() {
  return (
    <div className="flex min-h-screen">
      <nav aria-label="Main" className="flex w-56 flex-col gap-2 border-r border-gray-200 p-4">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) => (isActive ? 'font-bold' : 'font-normal')}
          >
            {link.label}
          </NavLink>
        ))}
      </nav>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}
