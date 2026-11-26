import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { errorText, useLoad } from '../../lib/useLoad';
import { PeopleTab } from './PeopleTab';
import { RecapTab } from './RecapTab';
import {
  audioUrl,
  getPeople,
  getRecap,
  getTranscript,
  type MeetingDetail,
  type Segment,
} from './report-api';
import { SidePanel } from './SidePanel';
import { TranscriptTab } from './TranscriptTab';

const TABS = [
  { key: 'recap', label: 'Recap' },
  { key: 'transcript', label: 'Transcript' },
  { key: 'people', label: 'People' },
] as const;
type TabKey = (typeof TABS)[number]['key'];

function parseTab(value: string | null): TabKey {
  return TABS.find((t) => t.key === value)?.key ?? 'recap';
}

function parseSeconds(value: string | null): number | null {
  if (value === null || value.trim() === '') return null;
  const n = Number(value);
  return Number.isFinite(n) && n >= 0 ? n : null;
}

function currentSegment(segments: Segment[], seconds: number): Segment | null {
  const ms = seconds * 1000;
  let found: Segment | null = null;
  for (const s of segments) {
    if (s.start_ms <= ms) found = s;
    else break;
  }
  return found;
}

interface ReportViewProps {
  meeting: MeetingDetail;
  onParticipantRenamed: (participantId: string, name: string) => void;
}

function LoadError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 text-bad">
      <span>{message}</span>
      <button
        type="button"
        onClick={onRetry}
        className="h-[34px] cursor-pointer rounded-control border border-line bg-surface px-3 text-[0.85rem] font-semibold text-ink hover:bg-sunken"
      >
        Retry
      </button>
    </div>
  );
}

export function ReportView({ meeting, onParticipantRenamed }: ReportViewProps) {
  const id = meeting.id;
  const [params, setParams] = useSearchParams();
  const tab = parseTab(params.get('tab'));
  const tParam = params.get('t');

  const audioRef = useRef<HTMLAudioElement>(null);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [audioTotal, setAudioTotal] = useState(0);
  const [rate, setRate] = useState(1);

  const loadRecap = useCallback(() => getRecap(id), [id]);
  const loadTranscript = useCallback(() => getTranscript(id), [id]);
  const loadPeople = useCallback(() => getPeople(id), [id]);
  const recap = useLoad(loadRecap);
  const transcript = useLoad(loadTranscript);
  const people = useLoad(loadPeople);

  const segments = useMemo(() => transcript.data?.segments ?? [], [transcript.data]);
  const current = currentSegment(segments, time);
  const metaTotal = meeting.duration_ms ? meeting.duration_ms / 1000 : 0;
  const total = metaTotal > 0 ? metaTotal : audioTotal;

  const seek = useCallback((seconds: number) => {
    const audio = audioRef.current;
    if (audio) audio.currentTime = Math.max(0, seconds);
  }, []);

  const seekAndPlay = useCallback(
    (seconds: number) => {
      seek(seconds);
      const audio = audioRef.current;
      if (audio) void Promise.resolve(audio.play()).catch(() => undefined);
    },
    [seek],
  );

  // Deep link: ?t=<seconds> seeks on load and whenever it changes.
  useEffect(() => {
    const seconds = parseSeconds(tParam);
    if (seconds !== null) seek(seconds);
  }, [tParam, seek]);

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (!playing) void Promise.resolve(audio.play()).catch(() => undefined);
    else audio.pause();
  };

  const changeRate = (next: number) => {
    setRate(next);
    if (audioRef.current) audioRef.current.playbackRate = next;
  };

  const setTab = (key: TabKey) =>
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('tab', key);
      return next;
    });

  const syncTime = () => {
    if (audioRef.current) setTime(audioRef.current.currentTime);
  };

  const renamed = (participantId: string, name: string) => {
    onParticipantRenamed(participantId, name);
    people.reload();
    transcript.reload();
  };

  return (
    <div className="grid grid-cols-[minmax(0,1fr)_340px] items-start gap-5 max-[980px]:grid-cols-1">
      <audio
        ref={audioRef}
        hidden
        preload="metadata"
        src={audioUrl(id)}
        onTimeUpdate={syncTime}
        onSeeked={syncTime}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
        onLoadedMetadata={() => {
          const d = audioRef.current?.duration ?? 0;
          if (Number.isFinite(d)) setAudioTotal(d);
        }}
      />
      <div className="flex min-w-0 flex-col gap-4">
        <div
          role="tablist"
          aria-label="Report sections"
          className="flex gap-1 border-b border-line"
        >
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

        {tab === 'recap' &&
          (recap.data ? (
            <RecapTab meetingId={id} recap={recap.data} onChange={recap.update} />
          ) : recap.error ? (
            <LoadError message={errorText(recap.error)} onRetry={recap.reload} />
          ) : (
            <p className="text-muted">Loading recap</p>
          ))}

        {tab === 'transcript' &&
          (transcript.data ? (
            <TranscriptTab
              segments={segments}
              currentId={current?.id ?? null}
              playing={playing}
              onSeek={seek}
            />
          ) : transcript.error ? (
            <LoadError message={errorText(transcript.error)} onRetry={transcript.reload} />
          ) : (
            <p className="text-muted">Loading transcript</p>
          ))}

        {tab === 'people' &&
          (people.data ? (
            <PeopleTab meetingId={id} people={people.data.people} onRenamed={renamed} />
          ) : people.error ? (
            <LoadError message={errorText(people.error)} onRetry={people.reload} />
          ) : (
            <p className="text-muted">Loading people</p>
          ))}
      </div>

      <SidePanel
        meetingId={id}
        speaker={current?.speaker ?? null}
        fallbackName={meeting.title}
        playing={playing}
        time={time}
        total={total}
        rate={rate}
        chapters={recap.data?.chapters ?? []}
        onToggle={togglePlay}
        onBack={() => seek(time - 15)}
        onSeek={seek}
        onRate={changeRate}
        onChapter={seekAndPlay}
      />
    </div>
  );
}
