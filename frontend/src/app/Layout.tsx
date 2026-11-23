import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Rail } from './Rail';
import { placeholderOrg, placeholderRole, placeholderUser, type Role } from './session';

export interface LayoutContext {
  role: Role;
}

export default function Layout() {
  // Preview role is local state only.
  const [role, setRole] = useState<Role>(placeholderRole);
  const context: LayoutContext = { role };

  return (
    <div className="grid min-h-screen grid-cols-[248px_minmax(0,1fr)] max-[860px]:grid-cols-1">
      <Rail
        user={placeholderUser}
        org={placeholderOrg}
        role={role}
        followUpCount={0}
        onToggleRole={() => setRole((r) => (r === 'owner' ? 'member' : 'owner'))}
      />
      <main className="flex w-full max-w-[1160px] min-w-0 flex-col gap-[22px] px-6 pt-[30px] pb-[72px] pl-8 max-[860px]:px-4 max-[860px]:pt-5">
        <Outlet context={context} />
      </main>
    </div>
  );
}
