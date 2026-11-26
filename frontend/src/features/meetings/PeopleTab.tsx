import { useState } from 'react';
import { Avatar } from '../../components/Avatar';
import { useToast } from '../../components/toast-context';
import { errorText } from '../../lib/useLoad';
import { renameParticipant, type Person } from './report-api';
import { card, emptyNote } from './report-styles';

interface PeopleTabProps {
  meetingId: string;
  people: Person[];
  onRenamed: (participantId: string, name: string) => void;
}

function PersonRow({
  person,
  editing,
  onEdit,
  onSave,
  onCancel,
}: {
  person: Person;
  editing: boolean;
  onEdit: () => void;
  onSave: (name: string) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState(person.display_name);
  const pct = Math.round(person.share * 100);
  return (
    <li className="flex items-center gap-3">
      <Avatar name={person.display_name} />
      <div className="w-[170px] flex-none max-[560px]:w-[110px]">
        {editing ? (
          <input
            autoFocus
            aria-label="Participant name"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') onSave(draft.trim());
              else if (e.key === 'Escape') onCancel();
            }}
            onBlur={onCancel}
            className="h-8 w-full rounded-control border border-accent-line bg-bg px-2 text-ink"
          />
        ) : (
          <button
            type="button"
            title="Click to rename"
            onClick={() => {
              setDraft(person.display_name);
              onEdit();
            }}
            className="max-w-full cursor-pointer truncate border-0 bg-transparent p-0 text-left font-semibold text-ink hover:text-accent"
          >
            {person.display_name}
          </button>
        )}
      </div>
      <div
        role="progressbar"
        aria-label={`${person.display_name} talk share`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        className="h-2.5 min-w-0 flex-1 overflow-hidden rounded-full bg-sunken"
      >
        <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-11 flex-none text-right font-mono text-[0.85rem] text-muted">{pct}%</span>
    </li>
  );
}

export function PeopleTab({ meetingId, people, onRenamed }: PeopleTabProps) {
  const toast = useToast();
  const [editingId, setEditingId] = useState<string | null>(null);

  const save = async (person: Person, name: string) => {
    setEditingId(null);
    if (!name || name === person.display_name) return;
    try {
      await renameParticipant(meetingId, person.participant_id, name);
      onRenamed(person.participant_id, name);
    } catch (error) {
      toast(errorText(error));
    }
  };

  return (
    <section className={card} aria-labelledby="who-spoke">
      <h2 id="who-spoke" className="mb-3 text-[1.02rem]">
        Who spoke
      </h2>
      {people.length === 0 ? (
        <p className={emptyNote}>None found.</p>
      ) : (
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {people.map((p) => (
            <PersonRow
              key={p.participant_id}
              person={p}
              editing={editingId === p.participant_id}
              onEdit={() => setEditingId(p.participant_id)}
              onSave={(name) => void save(p, name)}
              onCancel={() => setEditingId(null)}
            />
          ))}
        </ul>
      )}
    </section>
  );
}
