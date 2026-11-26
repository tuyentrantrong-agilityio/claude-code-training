import { Navigate, Outlet } from 'react-router-dom';
import { useMe } from './useMe';

export default function RequireAuth() {
  const { status } = useMe();
  if (status === 'loading') {
    return (
      <div role="status" className="grid min-h-screen place-items-center text-muted">
        Loading
      </div>
    );
  }
  if (status === 'signed-out') return <Navigate to="/sign-in" replace />;
  return <Outlet />;
}
