import { useNavigate } from 'react-router-dom';
import { fmtT } from '../lib/format';

interface TimeStampProps {
  meetingId: string;
  at: number;
  label?: string;
}

/** Button showing mm:ss that jumps to that moment in a meeting. */
export function TimeStamp({ meetingId, at, label }: TimeStampProps) {
  const navigate = useNavigate();
  return (
    <button
      type="button"
      title={label}
      aria-label={label ?? `Jump to ${fmtT(at)}`}
      onClick={(e) => {
        e.stopPropagation();
        navigate(`/meetings/${meetingId}?t=${Math.max(0, Math.floor(at))}`);
      }}
      className="cursor-pointer rounded-md border-0 bg-mark px-[7px] py-px font-mono text-xs font-medium text-mark-ink"
    >
      {fmtT(at)}
    </button>
  );
}
