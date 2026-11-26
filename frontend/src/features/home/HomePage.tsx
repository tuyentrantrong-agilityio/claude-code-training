import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useFollowUpCount } from '../../app/followUpCount';
import { useMe } from '../../app/useMe';
import { AvatarStack } from '../../components/AvatarStack';
import { EmptyState } from '../../components/EmptyState';
import { Icon, type IconName } from '../../components/Icon';
import { PageHeader } from '../../components/PageHeader';
import { TimeStamp } from '../../components/TimeStamp';
import { useToast } from '../../components/toast-context';
import { fmtDay, greeting } from '../../lib/format';
import { errorText, useLoad } from '../../lib/useLoad';
import { setFollowUpState, type FollowUpItem, type FollowUpState } from '../follow-ups/api';
import type { MeetingSummary } from '../meetings/api';
import { card, cardTitle, subtleButton } from '../meetings/report-styles';
import { getHome, type HomeData } from './api';

const starts: { to: string; icon: IconName; title: string; text: string; tone: string }[] = [
  {
    to: '/connections',
    icon: 'cal',
    title: 'Connect your calendar',
    text: 'The notetaker joins your Meet and Zoom calls.',
    tone: 'bg-tone0-bg text-tone0-fg',
  },
  {
    to: '/desktop',
    icon: 'screen',
    title: 'Install the desktop app',
    text: 'Record any call from your computer.',
    tone: 'bg-tone1-bg text-tone1-fg',
  },
  {
    to: '/meetings?upload=1',
    icon: 'up',
    title: 'Upload a recording',
    text: 'Try it on a file you already have.',
    tone: 'bg-tone2-bg text-tone2-fg',
  },
];

function StartCards() {
  return (
    <EmptyState
      title="Nothing here yet"
      text="Recapz writes the recap, finds the follow-ups and answers your questions. Start with any one of these."
    >
      <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-4 text-left">
        {starts.map((s) => (
          <Link
            key={s.to}
            to={s.to}
            className="flex items-center gap-3.5 rounded-[14px] border border-line bg-surface px-4 py-3.5 text-ink no-underline shadow-card hover:border-accent-line hover:bg-accent-soft"
          >
            <span className={`grid h-11 w-11 flex-none place-items-center rounded-[9px] ${s.tone}`}>
              <Icon name={s.icon} />
            </span>
            <span className="flex min-w-0 flex-col gap-0.5">
              <b>{s.title}</b>
              <span className="text-muted">{s.text}</span>
            </span>
          </Link>
        ))}
      </div>
    </EmptyState>
  );
}

function AskBar() {
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const q = text.trim();
    if (q) navigate(`/ask?q=${encodeURIComponent(q)}`);
  };
  return (
    <form
      onSubmit={submit}
      className="flex items-center gap-2.5 rounded-[14px] border border-line bg-surface px-3.5 py-2 shadow-card"
    >
      <Icon name="spark" className="h-[18px] w-[18px] flex-none text-accent" />
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        aria-label="Ask about your meetings"
        placeholder="Ask about your meetings. For example: what did we decide about the release?"
        className="h-9 min-w-0 flex-1 border-0 bg-transparent text-ink outline-none"
      />
      <button
        type="submit"
        className="inline-flex h-[34px] cursor-pointer items-center rounded-control border-0 bg-accent px-3.5 text-[0.88rem] font-semibold text-accent-ink"
      >
        Ask
      </button>
    </form>
  );
}

function NeedsYou({ items }: { items: FollowUpItem[] }) {
  const toast = useToast();
  const { refresh } = useFollowUpCount();
  const [states, setStates] = useState<Record<string, FollowUpState>>({});

  const toggle = async (item: FollowUpItem) => {
    const was = states[item.id] ?? item.state;
    const next: FollowUpState = was === 'done' ? 'open' : 'done';
    setStates((s) => ({ ...s, [item.id]: next }));
    try {
      await setFollowUpState(item.id, next);
      refresh();
    } catch (e) {
      setStates((s) => ({ ...s, [item.id]: was }));
      toast(errorText(e));
    }
  };

  return (
    <section className={`${card} flex flex-col gap-3`} aria-label="Needs you">
      <div className="flex items-center justify-between gap-3">
        <h2 className={cardTitle}>Needs you</h2>
        <Link to="/follow-ups" className="text-[0.85rem] font-semibold text-accent">
          See all follow-ups
        </Link>
      </div>
      {items.length === 0 ? (
        <div>
          <b>You are all caught up.</b>
          <p className="m-0 text-muted">Nothing is waiting on you right now.</p>
        </div>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
          {items.map((f) => {
            const state = states[f.id] ?? f.state;
            return (
              <li key={f.id} className="flex items-start gap-3">
                <label className="flex min-w-0 flex-1 cursor-pointer items-start gap-3">
                  <input
                    type="checkbox"
                    checked={state === 'done'}
                    onChange={() => void toggle(f)}
                    className="mt-1 h-4 w-4 flex-none accent-accent"
                  />
                  <span className="flex min-w-0 flex-col">
                    <span className={state === 'done' ? 'text-muted line-through' : ''}>
                      {f.text}
                    </span>
                    <small className="text-muted">{f.meeting_title}</small>
                  </span>
                </label>
                {f.at_ms !== null && <TimeStamp meetingId={f.meeting_id} at={f.at_ms / 1000} />}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function UpNext() {
  return (
    <section className={`${card} flex flex-col items-start gap-3`} aria-label="Up next">
      <h2 className={cardTitle}>Up next</h2>
      <p className="m-0 text-muted">Connect your calendar to see upcoming meetings here.</p>
      <button type="button" className={subtleButton} disabled title="Comes later">
        Connect calendar
      </button>
    </section>
  );
}

function meetingMeta(m: MeetingSummary): string {
  const parts: string[] = [];
  const date = m.started_at ? new Date(m.started_at) : null;
  if (date && !Number.isNaN(date.getTime())) parts.push(fmtDay(date));
  if (m.duration_ms) parts.push(`${Math.max(1, Math.round(m.duration_ms / 60000))} min`);
  return parts.join(' . ');
}

function RecentMeetings({ items }: { items: MeetingSummary[] }) {
  return (
    <section className="flex flex-col gap-3" aria-label="Recent meetings">
      <div className="flex items-center justify-between gap-3">
        <h2 className={cardTitle}>Recent meetings</h2>
        <Link to="/meetings" className="text-[0.85rem] font-semibold text-accent">
          All meetings
        </Link>
      </div>
      {items.length === 0 ? (
        <p className="text-muted">No meetings are ready yet.</p>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-4">
          {items.map((m) => (
            <Link
              key={m.id}
              to={`/meetings/${m.id}`}
              className={`${card} flex flex-col gap-2 text-ink no-underline hover:border-accent-line`}
            >
              <small className="text-muted">{meetingMeta(m)}</small>
              <b>{m.title}</b>
              {m.summary_preview && (
                <span className="line-clamp-3 text-muted">{m.summary_preview}</span>
              )}
              <span className="mt-auto flex items-center justify-between gap-2 pt-1">
                <AvatarStack names={m.participants.map((p) => p.display_name)} />
                <span className="rounded-full bg-sunken px-2.5 py-0.5 text-[0.78rem] font-semibold text-muted">
                  {m.folder?.name ?? 'Unfiled'}
                </span>
              </span>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

function HomeBody({ data }: { data: HomeData }) {
  if (!data.has_any_meeting) return <StartCards />;
  const needs = data.needs_you.filter((f) => f.state === 'open').slice(0, 4);
  return (
    <>
      <div className="grid grid-cols-[minmax(0,3fr)_minmax(0,2fr)] gap-4 max-[860px]:grid-cols-1">
        <NeedsYou items={needs} />
        <UpNext />
      </div>
      <RecentMeetings items={data.recent_meetings.slice(0, 3)} />
      <Link
        to="/week"
        className="flex items-center gap-3 rounded-[14px] border border-accent-line bg-accent-soft px-4 py-3.5 font-semibold text-accent no-underline"
      >
        <Icon name="cal" />
        Your week at a glance
      </Link>
    </>
  );
}

export default function HomePage() {
  const { me } = useMe();
  const now = new Date();
  const first = (me?.user.name ?? '').split(' ')[0];
  const { data, error, loading, reload } = useLoad(getHome);
  return (
    <>
      <PageHeader title={`${greeting(now)}, ${first}`} subtitle={fmtDay(now)} />
      <AskBar />
      {error ? (
        <div role="alert" className="flex flex-wrap items-center gap-3 text-bad">
          <span>{errorText(error)}</span>
          <button type="button" onClick={reload} className={subtleButton}>
            Retry
          </button>
        </div>
      ) : loading || !data ? (
        <p className="text-muted">Loading your home</p>
      ) : (
        <HomeBody data={data} />
      )}
    </>
  );
}
