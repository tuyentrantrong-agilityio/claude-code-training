export interface FolderChip {
  id: string;
  label: string;
}

interface FolderChipsProps {
  chips: FolderChip[];
  selected: string;
  onSelect: (id: string) => void;
  label?: string;
}

export function FolderChips({ chips, selected, onSelect, label = 'Folders' }: FolderChipsProps) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-2">
      {chips.map((chip) => {
        const on = chip.id === selected;
        return (
          <button
            key={chip.id}
            type="button"
            aria-pressed={on}
            onClick={() => onSelect(chip.id)}
            className={`h-8 cursor-pointer rounded-full border px-3.5 text-[0.85rem] font-semibold ${
              on
                ? 'border-accent-line bg-accent-soft text-accent'
                : 'border-line bg-surface text-muted hover:text-ink'
            }`}
          >
            {chip.label}
          </button>
        );
      })}
    </div>
  );
}
