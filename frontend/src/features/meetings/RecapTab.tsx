import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFollowUpCount } from '../../app/followUpCount';
import { TimeStamp } from '../../components/TimeStamp';
import { useToast } from '../../components/toast-context';
import { errorText } from '../../lib/useLoad';
import { setFollowUpState, type FollowUpState } from '../follow-ups/api';
import { saveSummary, type Recap } from './report-api';
import { card, cardTitle, emptyNote, primaryButton, subtleButton } from './report-styles';

interface RecapTabProps {
  meetingId: string;
  recap: Recap;
  onChange: (change: (recap: Recap) => Recap) => void;
}

function SummaryCard({ meetingId, recap, onChange }: RecapTabProps) {
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);

  const startEdit = () => {
    setDraft(recap.summary ?? '');
    setEditing(true);
  };

  const save = async () => {
    setSaving(true);
    try {
      await saveSummary(meetingId, draft);
      onChange((r) => ({ ...r, summary: draft, summary_edited_at: new Date().toISOString() }));
      setEditing(false);
    } catch (error) {
      toast(errorText(error));
    } finally {
      setSaving(false);
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(recap.summary ?? '');
      toast('Summary copied');
    } catch {
      toast('Could not copy the summary');
    }
  };

  return (
    <section className={card} aria-labelledby="summary-title">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h2 id="summary-title" className={cardTitle}>
          Summary
        </h2>
        {recap.summary_edited_at && !editing && <small className="text-muted">Edited</small>}
        <span className="flex-1" />
        {editing ? (
          <>
            <button type="button" className={subtleButton} onClick={() => setEditing(false)}>
              Cancel
            </button>
            <button
              type="button"
              className={primaryButton}
              disabled={saving}
              onClick={() => void save()}
            >
              Save
            </button>
          </>
        ) : (
          <>
            <button type="button" className={subtleButton} onClick={startEdit}>
              Edit
            </button>
            <button
              type="button"
              className={subtleButton}
              disabled={!recap.summary}
              onClick={() => void copy()}
            >
              Copy
            </button>
          </>
        )}
      </div>
      {editing ? (
        <textarea
          aria-label="Summary text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={7}
          className="w-full rounded-control border border-line bg-bg p-3 text-ink"
        />
      ) : recap.summary ? (
        <p className="whitespace-pre-wrap">{recap.summary}</p>
      ) : (
        <p className={emptyNote}>None found.</p>
      )}
    </section>
  );
}

function FollowUpsCard({ meetingId, recap, onChange }: RecapTabProps) {
  const toast = useToast();
  const { refresh } = useFollowUpCount();

  const setState = (id: string, state: FollowUpState) =>
    onChange((r) => ({
      ...r,
      follow_ups: r.follow_ups.map((f) => (f.id === id ? { ...f, state } : f)),
    }));

  const toggle = async (id: string, was: FollowUpState) => {
    const next: FollowUpState = was === 'done' ? 'open' : 'done';
    setState(id, next);
    try {
      await setFollowUpState(id, next);
      refresh();
    } catch (error) {
      setState(id, was);
      toast(errorText(error));
    }
  };

  return (
    <section className={card} aria-labelledby="followups-title">
      <h2 id="followups-title" className={`${cardTitle} mb-3`}>
        Follow-ups
      </h2>
      {recap.follow_ups.length === 0 ? (
        <p className={emptyNote}>None found.</p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
          {recap.follow_ups.map((f) => (
            <li key={f.id} className="flex items-start gap-3">
              <label className="flex min-w-0 flex-1 cursor-pointer items-start gap-3">
                <input
                  type="checkbox"
                  checked={f.state === 'done'}
                  onChange={() => void toggle(f.id, f.state)}
                  className="mt-1 h-4 w-4 flex-none accent-accent"
                />
                <span className="flex min-w-0 flex-col">
                  <span className={f.state === 'done' ? 'text-muted line-through' : ''}>
                    {f.text}
                  </span>
                  <small className="text-muted">{f.owner_name ?? 'Unassigned'}</small>
                </span>
              </label>
              {f.at_ms !== null && <TimeStamp meetingId={meetingId} at={f.at_ms / 1000} />}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function KeyPointsCard({ meetingId, recap }: RecapTabProps) {
  return (
    <section className={card} aria-labelledby="keypoints-title">
      <h2 id="keypoints-title" className={`${cardTitle} mb-3`}>
        Key points
      </h2>
      {recap.key_points.length === 0 ? (
        <p className={emptyNote}>None found.</p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {recap.key_points.map((k) => (
            <li key={k.id} className="flex items-start gap-3">
              <div className="flex min-w-0 flex-1 flex-col">
                <b>{k.title}</b>
                <span className="text-muted">{k.text}</span>
              </div>
              {k.at_ms !== null && <TimeStamp meetingId={meetingId} at={k.at_ms / 1000} />}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function HighlightsCard({ meetingId, recap }: RecapTabProps) {
  const navigate = useNavigate();
  return (
    <section className={card} aria-labelledby="highlights-title">
      <h2 id="highlights-title" className={`${cardTitle} mb-3`}>
        Highlights and questions
      </h2>
      <h3 className="mb-2 text-[0.85rem] font-semibold text-muted">Highlights</h3>
      {recap.highlights.length === 0 ? (
        <p className={emptyNote}>None found.</p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
          {recap.highlights.map((h) => (
            <li key={h.id} className="flex items-start gap-3">
              <q className="min-w-0 flex-1">{h.text}</q>
              {h.at_ms !== null && <TimeStamp meetingId={meetingId} at={h.at_ms / 1000} />}
            </li>
          ))}
        </ul>
      )}
      <h3 className="mt-4 mb-2 text-[0.85rem] font-semibold text-muted">Questions raised</h3>
      {recap.questions.length === 0 ? (
        <p className={emptyNote}>None found.</p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {recap.questions.map((q) => (
            <li key={q.id}>
              <button
                type="button"
                onClick={() => navigate(`/ask?${new URLSearchParams({ q: q.text }).toString()}`)}
                className="w-full cursor-pointer rounded-control border border-line bg-bg px-3 py-2 text-left text-ink hover:border-accent-line hover:bg-accent-soft"
              >
                {q.text}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function RecapTab(props: RecapTabProps) {
  return (
    <div className="flex flex-col gap-4">
      <SummaryCard {...props} />
      <FollowUpsCard {...props} />
      <KeyPointsCard {...props} />
      <HighlightsCard {...props} />
    </div>
  );
}
