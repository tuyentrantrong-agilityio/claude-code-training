import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Modal } from '../../components/Modal';
import { PageHeader } from '../../components/PageHeader';
import { useToast } from '../../components/toast-context';
import { errorText, useLoad } from '../../lib/useLoad';
import { getMeeting } from '../meetings/report-api';
import { dangerButton, primaryButton, subtleButton } from '../meetings/report-styles';
import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  sendMessage,
  type Conversation,
} from './api';
import { ChatList } from './ChatList';
import { MessageView, type UiMessage } from './MessageView';

const STARTERS = [
  'What did we decide in the last meeting?',
  'List my open follow-ups',
  'What are the main risks discussed?',
  "Summarize this week's meetings",
];

const nowIso = () => new Date().toISOString();

export default function AskPage() {
  const toast = useToast();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const chatId = params.get('c');
  const meetingParam = params.get('meeting');
  const q = params.get('q');

  const chats = useLoad(listConversations);
  const reloadChats = chats.reload;

  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [scopeId, setScopeId] = useState<string | null>(null);
  const [loadingChat, setLoadingChat] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [draft, setDraft] = useState('');
  const [toDelete, setToDelete] = useState<Conversation | null>(null);

  const openedRef = useRef<string | null>(null); // chat whose messages are in state
  const runRef = useRef(0); // id of the current stream; older streams are ignored
  const abortRef = useRef<AbortController | null>(null);
  const sentQRef = useRef<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const cancelStream = useCallback(() => {
    runRef.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
  }, []);

  // Open the chat named in the URL (skip one we just created and hold in state).
  useEffect(() => {
    if (!chatId) {
      openedRef.current = null;
      cancelStream();
      setMessages([]);
      setScopeId(null);
      setChatError(null);
      setLoadingChat(false);
      return;
    }
    if (openedRef.current === chatId) return;
    cancelStream();
    let cancelled = false;
    setLoadingChat(true);
    setChatError(null);
    getConversation(chatId)
      .then((d) => {
        if (cancelled) return;
        openedRef.current = chatId;
        setMessages(d.messages);
        setScopeId(d.scope_meeting_id);
        setLoadingChat(false);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setMessages([]);
        setChatError(errorText(e));
        setLoadingChat(false);
      });
    return () => {
      cancelled = true;
    };
  }, [chatId, cancelStream]);

  useEffect(() => cancelStream, [cancelStream]);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: 'end' });
  }, [messages]);

  const send = useCallback(
    async (raw: string) => {
      const text = raw.trim();
      if (!text || abortRef.current) return;
      const run = ++runRef.current;
      const controller = new AbortController();
      abortRef.current = controller;
      setStreaming(true);
      const current = () => runRef.current === run;
      const answerId = `answer-${run}`;
      const patch = (change: (m: UiMessage) => UiMessage) =>
        setMessages((list) => list.map((m) => (m.id === answerId ? change(m) : m)));

      let shown = false; // true once the question and answer bubbles are in the list
      try {
        let id = chatId;
        if (!id) {
          const conv = await createConversation(meetingParam);
          if (!current()) return;
          id = conv.id;
          openedRef.current = id;
          setScopeId(conv.scope_meeting_id);
          setParams(
            (prev) => {
              const next = new URLSearchParams(prev);
              next.set('c', conv.id);
              next.delete('meeting');
              next.delete('q');
              return next;
            },
            { replace: true },
          );
          reloadChats();
        }
        setMessages((list) => [
          ...list,
          {
            id: `question-${run}`,
            role: 'user',
            text,
            status: 'done',
            created_at: nowIso(),
            citations: [],
          },
          {
            id: answerId,
            role: 'assistant',
            text: '',
            status: 'streaming',
            created_at: nowIso(),
            citations: [],
          },
        ]);
        shown = true;
        let finished = false;
        await sendMessage(
          id,
          text,
          {
            onToken: (t) => current() && patch((m) => ({ ...m, text: m.text + t })),
            onCitations: (items) => current() && patch((m) => ({ ...m, citations: items })),
            // Keep the local id so the bubble is not remounted when the answer completes.
            onDone: () => {
              finished = true;
              if (current()) patch((m) => ({ ...m, status: 'done' }));
            },
            onError: (message) => {
              finished = true;
              if (current()) patch((m) => ({ ...m, status: 'failed', error: message }));
            },
          },
          controller.signal,
        );
        if (current() && !finished) {
          patch((m) => ({ ...m, status: 'failed', error: 'The connection was lost.' }));
        }
      } catch (e) {
        if (!current()) return;
        if (controller.signal.aborted) {
          patch((m) => ({ ...m, status: 'done', text: m.text || 'Stopped.' }));
        } else if (shown) {
          patch((m) => ({ ...m, status: 'failed', error: errorText(e) }));
        } else {
          toast(errorText(e));
        }
      } finally {
        if (current()) {
          abortRef.current = null;
          setStreaming(false);
          reloadChats();
        }
      }
    },
    [chatId, meetingParam, reloadChats, setParams, toast],
  );

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (streaming || draft.trim() === '') return;
    const text = draft;
    setDraft('');
    void send(text);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  // ?q= sends once, then drops q from the URL. The timeout keeps a StrictMode
  // remount from sending twice.
  useEffect(() => {
    if (q === null) {
      sentQRef.current = null;
      return;
    }
    if (sentQRef.current === q) return;
    const timer = setTimeout(() => {
      sentQRef.current = q;
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.delete('q');
          return next;
        },
        { replace: true },
      );
      void send(q);
    }, 0);
    return () => clearTimeout(timer);
  }, [q, send, setParams]);

  const retry = (index: number) => {
    const question = messages[index - 1];
    if (!question || question.role !== 'user') return;
    setMessages((list) => list.filter((_, i) => i !== index && i !== index - 1));
    void send(question.text);
  };

  const confirmDelete = async () => {
    const chat = toDelete;
    if (!chat) return;
    setToDelete(null);
    try {
      await deleteConversation(chat.id);
      reloadChats();
      if (chat.id === chatId) navigate('/ask');
    } catch (e) {
      toast(errorText(e));
    }
  };

  const activeScope = chatId ? scopeId : meetingParam;
  const loadScope = useCallback(
    () => (activeScope ? getMeeting(activeScope) : Promise.resolve(null)),
    [activeScope],
  );
  const scope = useLoad(loadScope);
  const empty = !chatId && messages.length === 0;

  return (
    <>
      <PageHeader
        title="Ask"
        subtitle="Ask across all your meetings. Every answer points to the moment it came from."
      />
      <div className="grid grid-cols-[240px_minmax(0,1fr)] gap-5 max-[860px]:grid-cols-1">
        <ChatList
          items={chats.data?.items ?? null}
          error={chats.error}
          activeId={chatId}
          onDelete={setToDelete}
        />
        <section className="flex min-w-0 flex-col gap-3.5" aria-label="Conversation">
          {activeScope && (
            <div className="flex flex-wrap items-center gap-3 rounded-control border border-accent-line bg-accent-soft px-3.5 py-2">
              <span>
                Asking about: <b>{scope.data?.title ?? 'this meeting'}</b>
              </span>
              <Link to="/ask" className="text-[0.85rem] font-semibold text-accent">
                Ask across all meetings
              </Link>
            </div>
          )}

          {chatError && (
            <p role="alert" className="text-bad">
              {chatError}
            </p>
          )}
          {loadingChat && <p className="text-muted">Loading chat</p>}

          {empty && !streaming && (
            <div className="flex flex-col items-center gap-3.5 rounded-[18px] border border-line bg-surface px-5 py-9 text-center">
              <h2 className="text-[1.1rem]">What would you like to know?</h2>
              <div className="flex flex-wrap justify-center gap-2">
                {STARTERS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    className={subtleButton}
                    onClick={() => void send(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="flex flex-col gap-3" aria-live="polite">
            {messages.map((m, i) => (
              <MessageView
                key={m.id}
                message={m}
                retryDisabled={streaming}
                onRetry={() => retry(i)}
              />
            ))}
            <div ref={endRef} />
          </div>

          <form onSubmit={submit} className="flex items-end gap-2.5">
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKeyDown}
              rows={2}
              aria-label="Question"
              placeholder="Ask anything about your meetings"
              className="min-h-[52px] min-w-0 flex-1 resize-y rounded-control border border-line bg-surface px-3 py-2 text-ink"
            />
            {streaming && (
              <button
                type="button"
                className={subtleButton}
                onClick={() => abortRef.current?.abort()}
              >
                Stop
              </button>
            )}
            <button type="submit" className={primaryButton} disabled={streaming || !draft.trim()}>
              Ask
            </button>
          </form>
        </section>
      </div>

      {toDelete && (
        <Modal title="Delete this chat?" onClose={() => setToDelete(null)}>
          <p>
            <b>{toDelete.title || 'New chat'}</b> and its answers will be removed. This cannot be
            undone.
          </p>
          <div className="flex justify-end gap-2.5">
            <button type="button" className={subtleButton} onClick={() => setToDelete(null)}>
              Cancel
            </button>
            <button type="button" className={dangerButton} onClick={() => void confirmDelete()}>
              Delete
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
