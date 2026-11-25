import { Navigate, useSearchParams } from 'react-router-dom';
import { useMe } from '../../app/useMe';

function Mark() {
  return (
    <svg width="46" height="46" viewBox="0 0 44 44" aria-hidden="true">
      <rect width="44" height="44" rx="13" fill="var(--color-accent)" />
      <circle cx="22" cy="22" r="8" fill="#fff" />
      <circle cx="22" cy="22" r="3.2" fill="var(--color-accent)" />
    </svg>
  );
}

export default function SignInPage() {
  const { status } = useMe();
  const [params] = useSearchParams();
  const error = params.get('error');

  if (status === 'signed-in') return <Navigate to="/home" replace />;

  return (
    <div className="grid min-h-screen place-items-center p-4">
      <div className="flex w-[min(430px,100%)] flex-col items-center gap-3.5 rounded-[20px] border border-line bg-surface px-[30px] py-[34px] text-center shadow-card">
        <Mark />
        <h1 className="text-[1.65rem]">Sign in to Recapz</h1>
        <p className="text-muted">
          Use the Google account an admin invited. Workspace and personal accounts both work.
        </p>
        <a
          href="/api/v1/auth/google/start"
          className="flex h-[46px] w-full cursor-pointer items-center justify-center gap-3 rounded-xl border border-line bg-surface font-semibold text-ink no-underline hover:bg-sunken"
        >
          <span
            aria-hidden="true"
            className="inline-grid h-5 w-5 place-items-center rounded-full"
            style={{
              background: 'conic-gradient(#ea4335 0 25%, #fbbc05 0 50%, #34a853 0 75%, #4285f4 0)',
            }}
          >
            <i className="block h-3 w-3 rounded-full bg-surface" />
          </span>
          Continue with Google
        </a>
        {error === 'not_invited' && (
          <div
            role="alert"
            className="w-full rounded-xl bg-sunken px-[15px] py-[11px] text-left text-[0.88rem] text-muted"
          >
            <b>This account is not invited.</b> Ask an admin to invite that exact email address,
            then try again. No account was created.
          </div>
        )}
        {error && error !== 'not_invited' && (
          <div
            role="alert"
            className="w-full rounded-xl bg-bad-bg px-[15px] py-[11px] text-left text-[0.88rem] text-bad"
          >
            Google sign-in did not complete. Please try again.
          </div>
        )}
      </div>
    </div>
  );
}
