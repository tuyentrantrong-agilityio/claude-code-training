import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { AvatarStack } from '../../components/AvatarStack';
import { EmptyState } from '../../components/EmptyState';
import { Icon } from '../../components/Icon';
import { PageHeader } from '../../components/PageHeader';
import { useToast } from '../../components/toast-context';
import {
  listMeetings,
  subscribeMeetingEvents,
  type MeetingStatus,
  type MeetingSummary,
  type StatusCounts,
} from './api';
import { FolderChips } from './FolderChips';
import { stageLabel } from './stages';
import { UploadModal } from './UploadModal';

const PAGE_SIZE = 20;
const SEARCH_DEBOUNCE_MS = 300;

const TABS: { status: MeetingStatus; label: string }[] = [
  { status: 'ready', label: 'Ready' },
  { status: 'processing', label: 'Processing' },
  { status: 'incomplete', label: 'Incomplete' },
];

interface ListData {
  key: string;
  items: MeetingSummary[];
  next: string | null;
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong';
}

function parseTab(value: string | null): MeetingStatus {
  return TABS.find((t) => t.status === value)?.status ?? 'ready';
}

const pill = 'rounded-full px-2.5 py-0.5 text-[0.78rem] font-semibold whitespace-nowrap';

function MeetingRow({ meeting }: { meeting: MeetingSummary }) {
  const date = meeting.started_at ? new Date(meeting.started_at) : null;
  const validDate = date && !Number.isNaN(date.getTime()) ? date : null;
  const names = meeting.participants.map((p) => p.display_name);

  let second: string;
  if (meeting.status === 'ready') second = meeting.summary_preview ?? '';
  else if (meeting.status === 'processing') second = `Working on it: ${stageLabel(meeting.stage)}`;
  else second = meeting.error ?? 'Processing stopped before the report was ready.';

  return (
    <Link
      to={`/meetings/${meeting.id}`}
      className="flex items-center gap-4 rounded-[14px] border border-line bg-surface px-4 py-3.5 text-ink no-underline shadow-card hover:border-accent-line hover:bg-accent-soft"
    >
      <span className="flex w-11 flex-none flex-col items-center leading-tight">
        <b className="text-[1.15rem]">{validDate ? validDate.getDate() : '-'}</b>
        <small className="text-muted">
          {validDate ? validDate.toLocaleDateString(undefined, { weekday: 'short' }) : ''}
        </small>
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <b className="truncate">{meeting.title}</b>
        <span className="truncate text-[0.9rem] text-muted">{second}</span>
      </span>
      {meeting.status === 'ready' && (
        <>
          {names.length > 0 && <AvatarStack names={names} />}
          <span className={`${pill} bg-sunken text-muted`}>
            {meeting.folder?.name ?? 'Unfiled'}
          </span>
        </>
      )}
      {meeting.status === 'processing' && (
        <span className={`${pill} bg-warn-bg text-warn`}>{stageLabel(meeting.stage)}</span>
      )}
      {meeting.status === 'incomplete' && (
        <span className={`${pill} bg-bad-bg text-bad`}>Incomplete</span>
      )}
    </Link>
  );
}

const primaryButton =
  'inline-flex h-[38px] cursor-pointer items-center gap-2 rounded-control border-0 bg-accent px-4 font-semibold text-accent-ink';

export default function MeetingsPage() {
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const tab = parseTab(params.get('tab'));
  const uploadOpen = params.get('upload') === '1';

  const [search, setSearch] = useState('');
  const [q, setQ] = useState('');
  const [version, setVersion] = useState(0);
  const [data, setData] = useState<ListData | null>(null);
  const [failure, setFailure] = useState<{ key: string; message: string } | null>(null);
  const [counts, setCounts] = useState<StatusCounts | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const inserted = useRef<MeetingSummary | null>(null);
  const subs = useRef(new Map<string, () => void>());
  const shown = useRef<MeetingSummary[]>([]);

  const key = `${tab}|${q}|${version}`;
  const current = data?.key === key ? data : null;
  const currentFailure = failure?.key === key ? failure : null;
  const loading = !current && !currentFailure;

  useEffect(() => {
    shown.current = current?.items ?? [];
  }, [current]);

  // Debounce the search box into the query used for fetching.
  useEffect(() => {
    const timer = setTimeout(() => setQ(search.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [search]);

  // Load the first page whenever the tab or query changes.
  useEffect(() => {
    let cancelled = false;
    const fetchKey = `${tab}|${q}|${version}`;
    listMeetings({ status: tab, q, limit: PAGE_SIZE })
      .then((res) => {
        if (cancelled) return;
        let items = res.items;
        const added = inserted.current;
        inserted.current = null;
        if (added && tab === 'processing' && !items.some((m) => m.id === added.id)) {
          items = [added, ...items];
        }
        setData({ key: fetchKey, items, next: res.next_cursor });
        setCounts(res.meta.counts);
      })
      .catch((error: unknown) => {
        if (!cancelled) setFailure({ key: fetchKey, message: errorText(error) });
      });
    return () => {
      cancelled = true;
    };
  }, [tab, q, version]);

  const refreshCounts = useCallback(() => {
    listMeetings({ status: 'processing', limit: 1 })
      .then((res) => setCounts(res.meta.counts))
      .catch(() => undefined);
  }, []);

  const onStage = useCallback((id: string, stage: string) => {
    setData((d) =>
      d ? { ...d, items: d.items.map((m) => (m.id === id ? { ...m, stage } : m)) } : d,
    );
  }, []);

  const onStatus = useCallback(
    (id: string, status: MeetingStatus, error: string | null) => {
      if (status === 'processing') return;
      const title = shown.current.find((m) => m.id === id)?.title ?? '';
      setData((d) => (d ? { ...d, items: d.items.filter((m) => m.id !== id) } : d));
      refreshCounts();
      if (status === 'ready') toast(`${title || 'Meeting'} is ready`);
      else if (error) toast(error);
    },
    [refreshCounts, toast],
  );

  // Subscribe to events for the meetings shown in the Processing tab.
  const processingIds =
    tab === 'processing' && current ? current.items.map((m) => m.id).join(',') : '';
  useEffect(() => {
    const want = new Set(processingIds.split(',').filter(Boolean));
    for (const [id, unsubscribe] of subs.current) {
      if (!want.has(id)) {
        unsubscribe();
        subs.current.delete(id);
      }
    }
    for (const id of want) {
      if (subs.current.has(id)) continue;
      subs.current.set(
        id,
        subscribeMeetingEvents(id, {
          onStage: (stage) => onStage(id, stage),
          onStatus: (status, error) => onStatus(id, status, error),
        }),
      );
    }
  }, [processingIds, onStage, onStatus]);

  useEffect(() => {
    const active = subs.current;
    return () => {
      for (const unsubscribe of active.values()) unsubscribe();
      active.clear();
    };
  }, []);

  const updateParams = (change: (next: URLSearchParams) => void) =>
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      change(next);
      return next;
    });

  const openUpload = () => updateParams((p) => p.set('upload', '1'));
  const closeUpload = useCallback(
    () =>
      setParams((prev) => {
        const next = new URLSearchParams(prev);
        next.delete('upload');
        return next;
      }),
    [setParams],
  );

  const onUploaded = (meeting: MeetingSummary) => {
    toast('Upload started. It shows as Processing.');
    setCounts((c) => (c ? { ...c, processing: c.processing + 1 } : c));
    if (tab === 'processing' && current) {
      setData({
        ...current,
        items: [meeting, ...current.items.filter((m) => m.id !== meeting.id)],
      });
    } else {
      inserted.current = meeting;
    }
    updateParams((p) => {
      p.set('tab', 'processing');
      p.delete('upload');
    });
  };

  const loadMore = async () => {
    if (!current?.next) return;
    const { key: startKey, next } = current;
    setLoadingMore(true);
    try {
      const res = await listMeetings({ status: tab, q, limit: PAGE_SIZE, cursor: next });
      setData((d) => {
        if (!d || d.key !== startKey) return d;
        const seen = new Set(d.items.map((m) => m.id));
        const more = res.items.filter((m) => !seen.has(m.id));
        return { ...d, items: [...d.items, ...more], next: res.next_cursor };
      });
      setCounts(res.meta.counts);
    } catch (error) {
      toast(errorText(error));
    } finally {
      setLoadingMore(false);
    }
  };

  const total = counts ? counts.ready + counts.processing + counts.incomplete : null;
  const noMeetingsAtAll = total === 0 && q === '' && !loading && !currentFailure;

  return (
    <>
      <PageHeader title="Meetings" subtitle="Every recorded meeting">
        <button type="button" onClick={openUpload} className={primaryButton}>
          <Icon name="up" />
          Upload
        </button>
      </PageHeader>

      {noMeetingsAtAll ? (
        <EmptyState
          title="No meetings yet"
          text="Recorded meetings appear here with a recap, follow-ups and a transcript."
        >
          <button type="button" onClick={openUpload} className={primaryButton}>
            <Icon name="up" />
            Upload
          </button>
        </EmptyState>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <input
              type="search"
              aria-label="Search meetings"
              placeholder="Search meetings"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-[38px] min-w-[220px] flex-1 rounded-control border border-line bg-surface px-3 text-ink"
            />
            <FolderChips chips={[{ id: 'all', label: 'All' }]} selected="all" onSelect={() => {}} />
          </div>

          <div
            role="tablist"
            aria-label="Meeting status"
            className="flex gap-1 border-b border-line"
          >
            {TABS.map((t) => {
              const on = t.status === tab;
              return (
                <button
                  key={t.status}
                  type="button"
                  role="tab"
                  aria-selected={on}
                  onClick={() => updateParams((p) => p.set('tab', t.status))}
                  className={`-mb-px cursor-pointer border-0 border-b-2 bg-transparent px-3.5 py-2 font-semibold ${
                    on
                      ? 'border-accent text-accent'
                      : 'border-transparent text-muted hover:text-ink'
                  }`}
                >
                  {t.label} {counts?.[t.status] ?? 0}
                </button>
              );
            })}
          </div>

          {loading && <p className="text-muted">Loading meetings</p>}

          {currentFailure && (
            <div role="alert" className="flex flex-wrap items-center gap-3 text-bad">
              <span>{currentFailure.message}</span>
              <button
                type="button"
                onClick={() => setVersion((v) => v + 1)}
                className="h-[34px] cursor-pointer rounded-control border border-line bg-surface px-3 text-[0.85rem] font-semibold text-ink hover:bg-sunken"
              >
                Retry
              </button>
            </div>
          )}

          {current && current.items.length === 0 && (
            <p className="text-muted">Nothing in this view.</p>
          )}

          {current && current.items.length > 0 && (
            <div className="flex flex-col gap-2.5">
              {current.items.map((m) => (
                <MeetingRow key={m.id} meeting={m} />
              ))}
            </div>
          )}

          {current?.next && (
            <div className="flex justify-center">
              <button
                type="button"
                disabled={loadingMore}
                onClick={() => void loadMore()}
                className="h-[38px] cursor-pointer rounded-control border border-line bg-surface px-4 font-semibold text-ink hover:bg-sunken disabled:cursor-default disabled:opacity-60"
              >
                Load more
              </button>
            </div>
          )}
        </>
      )}

      {uploadOpen && <UploadModal onClose={closeUpload} onUploaded={onUploaded} />}
    </>
  );
}
