import { useCallback, useState } from 'react';
import { useFollowUpCount } from '../../app/followUpCount';
import { EmptyState } from '../../components/EmptyState';
import { PageHeader } from '../../components/PageHeader';
import { TimeStamp } from '../../components/TimeStamp';
import { useToast } from '../../components/toast-context';
import { errorText, useLoad } from '../../lib/useLoad';
import { FolderChips } from '../meetings/FolderChips';
import { listFollowUps, setFollowUpState, type FollowUpOwner, type FollowUpState } from './api';

type Tab = 'todo' | 'suggested';

const TABS: { key: Tab; label: string }[] = [
  { key: 'todo', label: 'To do' },
  { key: 'suggested', label: 'Suggested' },
];

const OWNER_CHIPS = [
  { id: 'me', label: 'Mine' },
  { id: 'all', label: 'Everyone' },
];

function TodoList({ owner }: { owner: FollowUpOwner }) {
  const toast = useToast();
  const { refresh } = useFollowUpCount();
  const load = useCallback(() => listFollowUps(owner, 'open'), [owner]);
  const { data, error, loading, reload, update } = useLoad(load);

  const setState = (id: string, state: FollowUpState) =>
    update((d) => ({ items: d.items.map((i) => (i.id === id ? { ...i, state } : i)) }));

  const toggle = async (id: string, was: FollowUpState) => {
    const next: FollowUpState = was === 'done' ? 'open' : 'done';
    setState(id, next);
    try {
      await setFollowUpState(id, next);
      refresh();
    } catch (e) {
      setState(id, was);
      toast(errorText(e));
    }
  };

  if (error) {
    return (
      <div role="alert" className="flex flex-wrap items-center gap-3 text-bad">
        <span>{errorText(error)}</span>
        <button
          type="button"
          onClick={reload}
          className="h-[34px] cursor-pointer rounded-control border border-line bg-surface px-3 text-[0.85rem] font-semibold text-ink hover:bg-sunken"
        >
          Retry
        </button>
      </div>
    );
  }
  if (loading || !data) return <p className="text-muted">Loading follow-ups</p>;
  if (data.items.length === 0) {
    return <EmptyState title="Nothing to do" text="Follow-ups from your meetings land here." />;
  }

  return (
    <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
      {data.items.map((f) => (
        <li
          key={f.id}
          className="flex items-start gap-3 rounded-[14px] border border-line bg-surface px-4 py-3.5 shadow-card"
        >
          <label className="flex min-w-0 flex-1 cursor-pointer items-start gap-3">
            <input
              type="checkbox"
              checked={f.state === 'done'}
              onChange={() => void toggle(f.id, f.state)}
              className="mt-1 h-4 w-4 flex-none accent-accent"
            />
            <span className="flex min-w-0 flex-col">
              <span className={f.state === 'done' ? 'text-muted line-through' : ''}>{f.text}</span>
              <small className="text-muted">
                {f.owner_name ?? 'Unassigned'} . {f.meeting_title}
              </small>
            </span>
          </label>
          {f.at_ms !== null && <TimeStamp meetingId={f.meeting_id} at={f.at_ms / 1000} />}
        </li>
      ))}
    </ul>
  );
}

export default function FollowUpsPage() {
  const [tab, setTab] = useState<Tab>('todo');
  const [owner, setOwner] = useState<FollowUpOwner>('me');

  return (
    <>
      <PageHeader title="Follow-ups" subtitle="What needs doing, and what Recapz suggests" />

      <div role="tablist" aria-label="Follow-up views" className="flex gap-1 border-b border-line">
        {TABS.map((t) => {
          const on = t.key === tab;
          return (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => setTab(t.key)}
              className={`-mb-px cursor-pointer border-0 border-b-2 bg-transparent px-3.5 py-2 font-semibold ${
                on ? 'border-accent text-accent' : 'border-transparent text-muted hover:text-ink'
              }`}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {tab === 'todo' ? (
        <>
          <FolderChips
            label="Owner"
            chips={OWNER_CHIPS}
            selected={owner}
            onSelect={(id) => setOwner(id === 'all' ? 'all' : 'me')}
          />
          <TodoList owner={owner} />
        </>
      ) : (
        <EmptyState title="All reviewed" text="New suggestions appear after your next meeting." />
      )}
    </>
  );
}
