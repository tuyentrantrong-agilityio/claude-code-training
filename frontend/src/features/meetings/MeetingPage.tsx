import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { EmptyState } from '../../components/EmptyState';
import { Modal } from '../../components/Modal';
import { useToast } from '../../components/toast-context';
import { ApiError } from '../../lib/api';
import { errorText, useLoad } from '../../lib/useLoad';
import { deleteMeeting, retryMeeting, subscribeMeetingEvents } from './api';
import { MeetingHeader } from './MeetingHeader';
import { getMeeting, renameMeeting, type MeetingDetail } from './report-api';
import { ReportView } from './ReportView';
import { dangerButton, primaryButton, subtleButton } from './report-styles';
import { stageLabel, STAGE_ORDER } from './stages';

function Skeleton() {
  return (
    <div role="status" aria-label="Loading meeting" className="flex animate-pulse flex-col gap-4">
      <div className="h-4 w-48 rounded bg-sunken" />
      <div className="h-8 w-80 rounded bg-sunken" />
      <div className="grid grid-cols-[minmax(0,1fr)_340px] gap-5 max-[980px]:grid-cols-1">
        <div className="h-72 rounded-card bg-sunken" />
        <div className="h-72 rounded-card bg-sunken" />
      </div>
    </div>
  );
}

function Processing({ meeting }: { meeting: MeetingDetail }) {
  const index = STAGE_ORDER.indexOf(meeting.stage ?? '');
  const pct = ((index + 1) / STAGE_ORDER.length) * 100;
  return (
    <section className="flex flex-col gap-3 rounded-card border border-line bg-surface p-6 shadow-card">
      <b>Working on it: {stageLabel(meeting.stage)}</b>
      <div
        role="progressbar"
        aria-label="Processing progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
        className="h-2.5 overflow-hidden rounded-full bg-sunken"
      >
        <div
          className="h-full rounded-full bg-accent transition-[width]"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-muted">This page fills in when the report is ready.</p>
    </section>
  );
}

function Incomplete({
  meeting,
  onRetry,
  onDelete,
  busy,
}: {
  meeting: MeetingDetail;
  onRetry: () => void;
  onDelete: () => void;
  busy: boolean;
}) {
  return (
    <section className="flex flex-col gap-3 rounded-card border border-line bg-surface p-6 shadow-card">
      <p role="alert" className="text-bad">
        {meeting.error ?? 'Processing stopped before the report was ready.'}
      </p>
      <div className="flex flex-wrap gap-2.5">
        <button type="button" className={primaryButton} disabled={busy} onClick={onRetry}>
          Process what was saved
        </button>
        <button type="button" className={subtleButton} disabled={busy} onClick={onDelete}>
          Delete
        </button>
      </div>
    </section>
  );
}

export default function MeetingPage() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const load = useCallback(() => getMeeting(id), [id]);
  const { data: meeting, error, reload, update } = useLoad(load);
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const status = meeting?.status;
  // While processing, follow live events and reload the report when it is done.
  useEffect(() => {
    if (status !== 'processing') return;
    return subscribeMeetingEvents(id, {
      onStage: (stage) => update((m) => ({ ...m, stage })),
      onStatus: (next) => {
        if (next !== 'processing') reload();
      },
    });
  }, [id, status, update, reload]);

  if (error instanceof ApiError && error.status === 404) {
    return (
      <EmptyState title="Meeting not found" text="It may have been deleted.">
        <Link
          to="/meetings"
          className="inline-flex h-9 items-center rounded-control border border-accent bg-accent px-3.5 text-[0.9rem] font-semibold text-accent-ink no-underline"
        >
          Back to Meetings
        </Link>
      </EmptyState>
    );
  }
  if (error) {
    return (
      <div role="alert" className="flex flex-wrap items-center gap-3 text-bad">
        <span>{errorText(error)}</span>
        <button type="button" className={subtleButton} onClick={reload}>
          Retry
        </button>
      </div>
    );
  }
  if (!meeting) return <Skeleton />;

  const retry = async () => {
    setBusy(true);
    try {
      await retryMeeting(id);
      update((m) => ({ ...m, status: 'processing', stage: null, error: null }));
    } catch (e) {
      toast(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    try {
      await deleteMeeting(id);
      navigate('/meetings');
      toast('Meeting deleted');
    } catch (e) {
      toast(errorText(e));
      setConfirmDelete(false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <MeetingHeader
        meeting={meeting}
        onRename={async (title) => {
          await renameMeeting(id, title);
          update((m) => ({ ...m, title }));
        }}
      />
      {meeting.status === 'processing' && <Processing meeting={meeting} />}
      {meeting.status === 'incomplete' && (
        <Incomplete
          meeting={meeting}
          busy={busy}
          onRetry={() => void retry()}
          onDelete={() => setConfirmDelete(true)}
        />
      )}
      {meeting.status === 'ready' && (
        <ReportView
          meeting={meeting}
          onParticipantRenamed={(pid, name) =>
            update((m) => ({
              ...m,
              participants: m.participants.map((p) =>
                p.id === pid ? { ...p, display_name: name } : p,
              ),
            }))
          }
        />
      )}
      {confirmDelete && (
        <Modal title="Delete this meeting?" onClose={() => setConfirmDelete(false)}>
          <p className="text-muted">
            The recording, transcript and recap are removed. This cannot be undone.
          </p>
          <div className="flex justify-end gap-2.5">
            <button type="button" className={subtleButton} onClick={() => setConfirmDelete(false)}>
              Cancel
            </button>
            <button
              type="button"
              className={dangerButton}
              disabled={busy}
              onClick={() => void remove()}
            >
              Delete
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
