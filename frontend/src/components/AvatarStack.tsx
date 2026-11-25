import { Avatar } from './Avatar';

export function AvatarStack({ names, max = 4 }: { names: string[]; max?: number }) {
  const extra = names.length - max;
  const ring = 'border-2 border-surface -ml-2 first:ml-0';
  return (
    <span className="flex" aria-label={`${names.length} people`}>
      {names.slice(0, max).map((n) => (
        <Avatar key={n} name={n} className={ring} />
      ))}
      {extra > 0 && (
        <span
          aria-hidden="true"
          className={`inline-grid h-[30px] w-[30px] place-items-center rounded-full bg-tone0-bg text-[0.72rem] font-bold text-tone0-fg ${ring}`}
        >
          +{extra}
        </span>
      )}
    </span>
  );
}
