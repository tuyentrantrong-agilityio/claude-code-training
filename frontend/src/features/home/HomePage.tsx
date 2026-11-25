import { Link } from 'react-router-dom';
import { useMe } from '../../app/useMe';
import { EmptyState } from '../../components/EmptyState';
import { Icon, type IconName } from '../../components/Icon';
import { PageHeader } from '../../components/PageHeader';
import { fmtDay, greeting } from '../../lib/format';

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
    to: '/meetings',
    icon: 'up',
    title: 'Upload a recording',
    text: 'Try it on a file you already have.',
    tone: 'bg-tone2-bg text-tone2-fg',
  },
];

export default function HomePage() {
  const { me } = useMe();
  const now = new Date();
  const first = (me?.user.name ?? '').split(' ')[0];
  return (
    <>
      <PageHeader title={`${greeting(now)}, ${first}`} subtitle={fmtDay(now)} />
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
              <span
                className={`grid h-11 w-11 flex-none place-items-center rounded-[9px] ${s.tone}`}
              >
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
    </>
  );
}
