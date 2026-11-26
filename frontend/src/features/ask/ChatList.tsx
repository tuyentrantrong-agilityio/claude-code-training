import { Link } from 'react-router-dom';
import { errorText } from '../../lib/useLoad';
import { primaryButton } from '../meetings/report-styles';
import type { Conversation } from './api';

interface ChatListProps {
  items: Conversation[] | null;
  error: unknown;
  activeId: string | null;
  onDelete: (chat: Conversation) => void;
}

export function ChatList({ items, error, activeId, onDelete }: ChatListProps) {
  return (
    <aside className="flex min-w-0 flex-col gap-3" aria-label="Chats">
      <Link to="/ask" className={`${primaryButton} justify-center no-underline`}>
        New chat
      </Link>
      {error ? (
        <p role="alert" className="text-bad">
          {errorText(error)}
        </p>
      ) : items === null ? (
        <p className="text-muted">Loading chats</p>
      ) : items.length === 0 ? (
        <p className="text-muted">Your chats will be listed here.</p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-1 p-0">
          {items.map((c) => {
            const on = c.id === activeId;
            return (
              <li
                key={c.id}
                className={`flex items-center gap-1 rounded-control border pr-1 ${
                  on ? 'border-accent-line bg-accent-soft' : 'border-transparent hover:bg-sunken'
                }`}
              >
                <Link
                  to={`/ask?c=${c.id}`}
                  aria-current={on ? 'page' : undefined}
                  className={`min-w-0 flex-1 truncate px-2.5 py-2 text-ink no-underline ${
                    on ? 'font-semibold' : ''
                  }`}
                >
                  {c.title || 'New chat'}
                </Link>
                <button
                  type="button"
                  aria-label={`Delete chat ${c.title || 'New chat'}`}
                  title="Delete chat"
                  onClick={() => onDelete(c)}
                  className="h-6 w-6 flex-none cursor-pointer rounded-md border-0 bg-transparent text-muted hover:bg-sunken hover:text-bad"
                >
                  x
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </aside>
  );
}
