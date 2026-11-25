import { useEffect, useState, type FormEvent } from 'react';
import { useOutletContext } from 'react-router-dom';
import type { LayoutContext } from '../../app/Layout';
import { useMe, type Role } from '../../app/useMe';
import { EmptyState } from '../../components/EmptyState';
import { PageHeader } from '../../components/PageHeader';
import { useToast } from '../../components/toast-context';
import { Avatar } from '../../components/Avatar';
import { api, ApiError } from '../../lib/api';

interface Member {
  user_id: string;
  email: string;
  name: string;
  role: Role;
}

interface Invite {
  id: string;
  email: string;
  role: Role;
  expires_at: string;
}

const field =
  'h-[38px] rounded-control border border-line bg-surface px-3 text-ink disabled:opacity-60';
const ghostButton =
  'h-[34px] cursor-pointer rounded-control border border-line bg-surface px-3 text-[0.85rem] font-semibold text-ink hover:bg-sunken disabled:cursor-default disabled:opacity-60';

function errorText(error: unknown): string {
  return error instanceof ApiError || error instanceof Error
    ? error.message
    : 'Something went wrong';
}

function PeopleTab() {
  const toast = useToast();
  const { me } = useMe();
  const [members, setMembers] = useState<Member[]>([]);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<Role>('member');
  const [busy, setBusy] = useState(false);

  const [version, setVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([api<Member[]>('/admin/members'), api<Invite[]>('/admin/invites')])
      .then(([m, i]) => {
        if (cancelled) return;
        setMembers(m);
        setInvites(i);
      })
      .catch((error: unknown) => {
        if (!cancelled) toast(errorText(error));
      })
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [version, toast]);

  const run = async (action: () => Promise<unknown>, success: string) => {
    setBusy(true);
    try {
      await action();
      toast(success);
      setVersion((v) => v + 1);
      return true;
    } catch (error) {
      toast(errorText(error));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const onInvite = async (e: FormEvent) => {
    e.preventDefault();
    const address = email.trim();
    if (!address) return;
    const ok = await run(
      () => api('/admin/invites', { method: 'POST', body: { email: address, role } }),
      `Invited ${address}`,
    );
    if (ok) setEmail('');
  };

  return (
    <div className="flex flex-col gap-[18px]">
      <section className="flex flex-col gap-3 rounded-[16px] border border-line bg-surface p-[18px] shadow-card">
        <h2 className="text-[1.05rem]">Invite someone</h2>
        <form onSubmit={(e) => void onInvite(e)} className="flex flex-wrap gap-2.5">
          <input
            type="email"
            aria-label="Email"
            placeholder="name@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={`${field} min-w-[220px] flex-1`}
          />
          <select
            aria-label="Role"
            value={role}
            onChange={(e) => setRole(e.target.value as Role)}
            className={field}
          >
            <option value="member">member</option>
            <option value="owner">owner</option>
          </select>
          <button
            type="submit"
            disabled={!email.trim() || busy}
            className="h-[38px] cursor-pointer rounded-control border-0 bg-accent px-4 font-semibold text-accent-ink disabled:cursor-default disabled:opacity-50"
          >
            Invite
          </button>
        </form>
        <p className="text-[0.85rem] text-muted">
          People sign in with the Google account for that exact email address.
        </p>
      </section>

      <section className="flex flex-col gap-2.5 rounded-[16px] border border-line bg-surface p-[18px] shadow-card">
        <h2 className="text-[1.05rem]">Pending invites</h2>
        {invites.length === 0 && loaded && <p className="text-muted">No pending invites.</p>}
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {invites.map((invite) => (
            <li key={invite.id} className="flex flex-wrap items-center gap-2.5">
              <b className="min-w-0 flex-1 truncate">{invite.email}</b>
              <span className="text-muted">{invite.role}</span>
              <span className="text-[0.85rem] text-muted">
                expires {new Date(invite.expires_at).toLocaleDateString()}
              </span>
              <button
                type="button"
                className={ghostButton}
                disabled={busy}
                onClick={() =>
                  void run(
                    () => api(`/admin/invites/${invite.id}`, { method: 'DELETE' }),
                    `Revoked invite for ${invite.email}`,
                  )
                }
              >
                Revoke
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="flex flex-col gap-2.5 rounded-[16px] border border-line bg-surface p-[18px] shadow-card">
        <h2 className="text-[1.05rem]">Members</h2>
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="text-[0.8rem] text-muted">
              <th className="py-1.5 font-semibold">Person</th>
              <th className="py-1.5 font-semibold">Role</th>
              <th className="py-1.5" />
            </tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <tr key={m.user_id} className="border-t border-line">
                <td className="py-2">
                  <span className="flex items-center gap-2.5">
                    <Avatar name={m.name} />
                    <span className="flex min-w-0 flex-col">
                      <b className="truncate leading-tight">{m.name}</b>
                      <small className="truncate text-muted">{m.email}</small>
                    </span>
                  </span>
                </td>
                <td className="py-2">
                  <select
                    aria-label={`Role for ${m.email}`}
                    value={m.role}
                    disabled={busy}
                    onChange={(e) =>
                      void run(
                        () =>
                          api(`/admin/members/${m.user_id}`, {
                            method: 'PATCH',
                            body: { role: e.target.value },
                          }),
                        `Updated ${m.email}`,
                      )
                    }
                    className={field}
                  >
                    <option value="member">member</option>
                    <option value="owner">owner</option>
                  </select>
                </td>
                <td className="py-2 text-right">
                  <button
                    type="button"
                    className={ghostButton}
                    disabled={busy}
                    aria-label={`Remove ${m.email}`}
                    onClick={() =>
                      void run(
                        () => api(`/admin/members/${m.user_id}`, { method: 'DELETE' }),
                        m.user_id === me?.user.id
                          ? 'You left the organization'
                          : `Removed ${m.email}`,
                      )
                    }
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

export default function AdminPage() {
  const { role } = useOutletContext<LayoutContext>();
  const { me } = useMe();
  if (role !== 'owner') {
    return (
      <>
        <PageHeader title="Admin" />
        <EmptyState
          title="Only owners can open this page"
          text={
            me?.role === 'owner'
              ? 'Use the account menu to preview as an owner.'
              : 'Ask an owner of your organization for access.'
          }
        />
      </>
    );
  }
  return (
    <>
      <PageHeader title="Admin" subtitle="Manage who can sign in to this workspace." />
      <div role="tablist" aria-label="Admin sections" className="flex gap-2 border-b border-line">
        <button
          type="button"
          role="tab"
          aria-selected="true"
          className="-mb-px cursor-pointer border-0 border-b-2 border-accent bg-transparent px-3 py-2 font-semibold text-accent"
        >
          People
        </button>
      </div>
      <div role="tabpanel">
        <PeopleTab />
      </div>
    </>
  );
}
