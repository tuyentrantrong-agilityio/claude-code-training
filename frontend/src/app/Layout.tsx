import { useCallback, useEffect, useMemo, useState } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { getFollowUpCount } from '../features/follow-ups/api';
import { FollowUpCountContext } from './followUpCount';
import { Rail } from './Rail';
import { useMe, type Role } from './useMe';

export interface LayoutContext {
  role: Role;
}

export default function Layout() {
  const { me, signOut } = useMe();
  const navigate = useNavigate();
  // Preview role is local state only; null means "use the real role".
  const [preview, setPreview] = useState<Role | null>(null);
  const [followUpCount, setFollowUpCount] = useState(0);

  const refreshCount = useCallback(() => {
    getFollowUpCount()
      .then((res) => setFollowUpCount(res.open_mine))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    let cancelled = false;
    getFollowUpCount()
      .then((res) => {
        if (!cancelled) setFollowUpCount(res.open_mine);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const countValue = useMemo(
    () => ({ count: followUpCount, refresh: refreshCount }),
    [followUpCount, refreshCount],
  );
  if (!me) return null;

  const realRole = me.role;
  const role = preview ?? realRole;
  const context: LayoutContext = { role };

  const onSignOut = async () => {
    await signOut();
    navigate('/sign-in', { replace: true });
  };

  return (
    <div className="grid min-h-screen grid-cols-[248px_minmax(0,1fr)] max-[860px]:grid-cols-1">
      <Rail
        user={me.user}
        org={me.organization}
        role={role}
        followUpCount={followUpCount}
        canPreview={realRole === 'owner'}
        onToggleRole={() => setPreview(role === 'owner' ? 'member' : 'owner')}
        onSignOut={() => void onSignOut()}
      />
      <main className="flex w-full max-w-[1160px] min-w-0 flex-col gap-[22px] px-6 pt-[30px] pb-[72px] pl-8 max-[860px]:px-4 max-[860px]:pt-5">
        <FollowUpCountContext.Provider value={countValue}>
          <Outlet context={context} />
        </FollowUpCountContext.Provider>
      </main>
    </div>
  );
}
