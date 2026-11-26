import { useState, type FormEvent, type KeyboardEvent, type MouseEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Avatar } from '../../components/Avatar';
import { fmtT } from '../../lib/format';
import { card, cardTitle, primaryButton, subtleButton } from './report-styles';

const SPEEDS = [0.75, 1, 1.25, 1.5, 2];
const PROMPTS = ['Summarize this meeting', 'What are the follow-ups?', 'Who owns the next steps?'];

interface Chapter {
  id: string;
  title: string;
  at_ms: number;
}

interface PlayerProps {
  speaker: string | null;
  fallbackName: string;
  playing: boolean;
  time: number;
  total: number;
  rate: number;
  chapters: Chapter[];
  onToggle: () => void;
  onBack: () => void;
  onSeek: (seconds: number) => void;
  onRate: (rate: number) => void;
}

function Player(p: PlayerProps) {
  const { total, time } = p;
  const pct = total > 0 ? Math.min(100, (time / total) * 100) : 0;

  const onClick = (e: MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    if (rect.width <= 0 || total <= 0) return;
    const frac = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    p.onSeek(frac * total);
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'ArrowRight') p.onSeek(Math.min(total, time + 5));
    else if (e.key === 'ArrowLeft') p.onSeek(Math.max(0, time - 5));
  };

  return (
    <section className={`${card} flex flex-col items-center gap-3`} aria-label="Player">
      <Avatar name={p.speaker ?? p.fallbackName} size="xl" />
      <small className="min-h-[1.2em] text-muted">{p.speaker ?? ''}</small>
      <div className="flex items-center gap-2">
        <button type="button" className={primaryButton} onClick={p.onToggle}>
          {p.playing ? 'Pause' : 'Play'}
        </button>
        <button type="button" className={subtleButton} onClick={p.onBack}>
          -15s
        </button>
      </div>
      <div
        role="slider"
        tabIndex={0}
        aria-label="Seek"
        aria-valuemin={0}
        aria-valuemax={Math.round(total)}
        aria-valuenow={Math.round(time)}
        onClick={onClick}
        onKeyDown={onKey}
        className="relative h-3 w-full cursor-pointer rounded-full bg-sunken"
      >
        <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
        {total > 0 &&
          p.chapters.map((c) => (
            <span
              key={c.id}
              data-testid="chapter-mark"
              className="absolute top-0 h-full w-0.5 bg-surface"
              style={{ left: `${Math.min(100, (c.at_ms / 1000 / total) * 100)}%` }}
            />
          ))}
      </div>
      <div className="flex w-full items-center justify-between">
        <span className="font-mono text-[0.85rem] text-muted">
          {fmtT(time)} / {fmtT(total)}
        </span>
        <select
          aria-label="Playback speed"
          value={p.rate}
          onChange={(e) => p.onRate(Number(e.target.value))}
          className="h-8 rounded-control border border-line bg-surface px-2 text-ink"
        >
          {SPEEDS.map((s) => (
            <option key={s} value={s}>
              {s}x
            </option>
          ))}
        </select>
      </div>
    </section>
  );
}

function AskBox({ meetingId }: { meetingId: string }) {
  const navigate = useNavigate();
  const [text, setText] = useState('');

  const ask = (question: string) => {
    const q = question.trim();
    if (!q) return;
    navigate(`/ask?${new URLSearchParams({ q, meeting: meetingId }).toString()}`);
  };
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    ask(text);
  };

  return (
    <section className={`${card} flex flex-col gap-3`} aria-labelledby="ask-title">
      <h2 id="ask-title" className={cardTitle}>
        Ask about this meeting
      </h2>
      <div className="flex flex-wrap gap-2">
        {PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => ask(prompt)}
            className="cursor-pointer rounded-full border border-line bg-bg px-3 py-1 text-[0.82rem] font-medium text-ink hover:border-accent-line hover:bg-accent-soft"
          >
            {prompt}
          </button>
        ))}
      </div>
      <form onSubmit={onSubmit} className="flex gap-2">
        <input
          aria-label="Ask a question"
          placeholder="Ask a question"
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="h-[36px] min-w-0 flex-1 rounded-control border border-line bg-bg px-3 text-ink"
        />
        <button type="submit" className={primaryButton}>
          Ask
        </button>
      </form>
    </section>
  );
}

export function SidePanel({
  meetingId,
  chapters,
  onChapter,
  ...player
}: PlayerProps & { meetingId: string; onChapter: (seconds: number) => void }) {
  return (
    <aside className="flex flex-col gap-4">
      <Player {...player} chapters={chapters} />
      <section className={card} aria-labelledby="chapters-title">
        <h2 id="chapters-title" className={`${cardTitle} mb-2`}>
          Chapters
        </h2>
        {chapters.length === 0 ? (
          <p className="text-muted">None found.</p>
        ) : (
          <ul className="m-0 flex list-none flex-col gap-0.5 p-0">
            {chapters.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => onChapter(c.at_ms / 1000)}
                  className="flex w-full cursor-pointer items-center gap-3 rounded-control border-0 bg-transparent px-2 py-1.5 text-left text-ink hover:bg-sunken"
                >
                  <span className="min-w-0 flex-1 truncate">{c.title}</span>
                  <span className="rounded-md bg-mark px-[7px] py-px font-mono text-xs font-medium text-mark-ink">
                    {fmtT(c.at_ms / 1000)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
      <AskBox meetingId={meetingId} />
    </aside>
  );
}
