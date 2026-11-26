import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { AvatarStack } from '../../components/AvatarStack';
import { Icon } from '../../components/Icon';
import { useToast } from '../../components/toast-context';
import { errorText } from '../../lib/useLoad';
import { recapExportUrl, transcriptExportUrl, type MeetingDetail } from './report-api';
import { meetingMeta } from './meeting-meta';
import { subtleButton } from './report-styles';

const menuItem =
  'flex w-full items-center rounded-lg border-0 bg-transparent px-2.5 py-2 text-left font-medium text-ink no-underline hover:bg-sunken disabled:cursor-default disabled:text-muted disabled:hover:bg-transparent';

function MoreMenu({ meetingId }: { meetingId: string }) {
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

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className={`${subtleButton} h-[38px] gap-2`}
      >
        More
        <Icon name="chev" className="h-4 w-4 flex-none" />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute top-[calc(100%+6px)] right-0 z-30 flex min-w-[220px] flex-col rounded-xl border border-line bg-surface p-1.5 shadow-pop"
        >
          <a
            role="menuitem"
            className={menuItem}
            href={transcriptExportUrl(meetingId)}
            download
            onClick={() => setOpen(false)}
          >
            Download transcript
          </a>
          <a
            role="menuitem"
            className={menuItem}
            href={recapExportUrl(meetingId)}
            download
            onClick={() => setOpen(false)}
          >
            Download recap
          </a>
          {['Push to Slack', 'Push to Notion', 'Send to webhook'].map((label) => (
            <button
              key={label}
              type="button"
              role="menuitem"
              disabled
              title="Comes later"
              className={menuItem}
            >
              {label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

interface MeetingHeaderProps {
  meeting: MeetingDetail;
  onRename: (title: string) => Promise<void>;
}

export function MeetingHeader({ meeting, onRename }: MeetingHeaderProps) {
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const ready = meeting.status === 'ready';
  const meta = meetingMeta(meeting);
  const names = meeting.participants.map((p) => p.display_name);

  const commit = async () => {
    const title = draft.trim();
    setEditing(false);
    if (!title || title === meeting.title) return;
    try {
      await onRename(title);
    } catch (error) {
      toast(errorText(error));
    }
  };

  const titleNode = editing ? (
    <input
      autoFocus
      aria-label="Meeting title"
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') void commit();
        else if (e.key === 'Escape') setEditing(false);
      }}
      onBlur={() => setEditing(false)}
      className="h-10 w-full min-w-[260px] rounded-control border border-accent-line bg-surface px-3 text-[1.4rem] font-bold text-ink"
    />
  ) : (
    <button
      type="button"
      title="Click to rename"
      onClick={() => {
        setDraft(meeting.title);
        setEditing(true);
      }}
      className="cursor-pointer border-0 bg-transparent p-0 text-left font-[inherit] text-inherit hover:text-accent"
    >
      {meeting.title}
    </button>
  );

  return (
    <>
      <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-[0.9rem] text-muted">
        <Link to="/meetings" className="text-muted hover:text-accent">
          Meetings
        </Link>
        <span aria-hidden="true">/</span>
        <span className="truncate">{meeting.title}</span>
      </nav>
      <div className="flex flex-wrap items-start gap-3">
        <div className="flex min-w-0 flex-col gap-1.5">
          <h1 className="text-[1.65rem]">{titleNode}</h1>
          <div className="flex flex-wrap items-center gap-3 text-muted">
            {names.length > 0 && <AvatarStack names={names} />}
            {meta && <span>{meta}</span>}
          </div>
        </div>
        <span className="flex-1" />
        {ready && (
          <div className="flex flex-wrap items-center gap-2.5">
            <MoreMenu meetingId={meeting.id} />
            <button
              type="button"
              disabled
              title="Comes later"
              className={`${subtleButton} h-[38px]`}
            >
              Share
            </button>
          </div>
        )}
      </div>
    </>
  );
}
