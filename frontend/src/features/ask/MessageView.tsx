import { Link } from 'react-router-dom';
import { TimeStamp } from '../../components/TimeStamp';
import { subtleButton } from '../meetings/report-styles';
import type { ChatMessage } from './api';

export interface UiMessage extends ChatMessage {
  /** Error text for a failed answer (from the stream); history has none. */
  error?: string;
}

function Citations({ message }: { message: UiMessage }) {
  if (message.citations.length === 0) return null;
  return (
    <ul className="m-0 mt-2.5 flex list-none flex-wrap gap-2 p-0" aria-label="Sources">
      {message.citations.map((c, i) => (
        <li
          key={`${c.meeting_id}-${c.at_ms}-${i}`}
          className="inline-flex items-center gap-1.5 rounded-full border border-accent-line bg-accent-soft py-0.5 pr-1.5 pl-3 text-[0.82rem]"
        >
          <Link
            to={`/meetings/${c.meeting_id}?t=${Math.floor(c.at_ms / 1000)}`}
            className="font-semibold text-accent no-underline hover:underline"
          >
            {c.meeting_title}
          </Link>
          <TimeStamp meetingId={c.meeting_id} at={c.at_ms / 1000} />
        </li>
      ))}
    </ul>
  );
}

interface MessageViewProps {
  message: UiMessage;
  onRetry: () => void;
  retryDisabled: boolean;
}

export function MessageView({ message, onRetry, retryDisabled }: MessageViewProps) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <p className="m-0 max-w-[80%] rounded-[14px] bg-accent px-3.5 py-2.5 whitespace-pre-wrap text-accent-ink">
          {message.text}
        </p>
      </div>
    );
  }

  const thinking = message.status === 'streaming' && message.text === '';
  return (
    <div className="flex">
      <div className="max-w-[88%] rounded-[14px] border border-line bg-surface px-3.5 py-2.5 shadow-card">
        {thinking && <p className="m-0 text-muted">Thinking...</p>}
        {message.text !== '' && <p className="m-0 whitespace-pre-wrap">{message.text}</p>}
        {message.status === 'failed' && (
          <div role="alert" className="flex flex-wrap items-center gap-3 text-bad">
            <span>{message.error ?? 'This answer could not be completed.'}</span>
            <button
              type="button"
              className={subtleButton}
              onClick={onRetry}
              disabled={retryDisabled}
            >
              Retry
            </button>
          </div>
        )}
        {message.status !== 'failed' && <Citations message={message} />}
      </div>
    </div>
  );
}
