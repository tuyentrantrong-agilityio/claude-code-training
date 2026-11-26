import { fmtDay } from '../../lib/format';
import type { MeetingDetail } from './report-api';

/** "<weekday, month day> . <time> . <platform> . <N min>" with the parts that exist. */
export function meetingMeta(meeting: MeetingDetail): string {
  const parts: string[] = [];
  const date = meeting.started_at ? new Date(meeting.started_at) : null;
  if (date && !Number.isNaN(date.getTime())) {
    parts.push(fmtDay(date));
    // Some locales use narrow no-break spaces in times; normalize them.
    parts.push(
      date
        .toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
        .replace(/\s+/g, ' '),
    );
  }
  if (meeting.platform)
    parts.push(meeting.platform.charAt(0).toUpperCase() + meeting.platform.slice(1));
  if (meeting.duration_ms)
    parts.push(`${Math.max(1, Math.round(meeting.duration_ms / 60000))} min`);
  return parts.join(' . ');
}
