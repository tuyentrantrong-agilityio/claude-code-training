import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import { fmtT } from '../../lib/format';
import type { Segment } from './report-api';
import { card, emptyNote } from './report-styles';

interface TranscriptTabProps {
  segments: Segment[];
  currentId: string | null;
  playing: boolean;
  onSeek: (seconds: number) => void;
}

function escapeRegExp(text: string) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function Highlighted({ text, query }: { text: string; query: string }) {
  if (!query) return <>{text}</>;
  const parts = text.split(new RegExp(`(${escapeRegExp(query)})`, 'i'));
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <mark key={i} className="rounded-sm bg-mark px-0.5 text-mark-ink">
            {part}
          </mark>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  );
}

export function TranscriptTab({ segments, currentId, playing, onSeek }: TranscriptTabProps) {
  const [query, setQuery] = useState('');
  const listRef = useRef<HTMLUListElement>(null);
  const q = query.trim();

  const shown = useMemo(() => {
    if (!q) return segments;
    const needle = q.toLowerCase();
    return segments.filter((s) => s.text.toLowerCase().includes(needle));
  }, [segments, q]);

  // Keep the current line visible while playing.
  useEffect(() => {
    if (!playing) return;
    const el = listRef.current?.querySelector('[aria-current="true"]');
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [currentId, playing]);

  return (
    <div className={`${card} flex flex-col gap-3`}>
      <input
        type="search"
        aria-label="Search transcript"
        placeholder="Search transcript"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="h-[38px] rounded-control border border-line bg-bg px-3 text-ink"
      />
      {shown.length === 0 ? (
        <p className={emptyNote}>{q ? 'No lines match.' : 'No transcript yet.'}</p>
      ) : (
        <ul ref={listRef} className="m-0 flex list-none flex-col gap-0.5 p-0">
          {shown.map((s) => {
            const current = s.id === currentId;
            return (
              <li key={s.id}>
                <button
                  type="button"
                  aria-current={current ? 'true' : undefined}
                  onClick={() => onSeek(s.start_ms / 1000)}
                  className={`grid w-full cursor-pointer grid-cols-[48px_110px_minmax(0,1fr)] gap-3 rounded-control border-0 px-2.5 py-2 text-left text-ink max-[560px]:grid-cols-[48px_minmax(0,1fr)] ${
                    current ? 'bg-accent-soft' : 'bg-transparent hover:bg-sunken'
                  }`}
                >
                  <span className="font-mono text-xs text-muted">{fmtT(s.start_ms / 1000)}</span>
                  <b className="truncate text-[0.9rem]">{s.speaker ?? 'Unknown'}</b>
                  <span className="max-[560px]:col-span-2">
                    <Highlighted text={s.text} query={q} />
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
