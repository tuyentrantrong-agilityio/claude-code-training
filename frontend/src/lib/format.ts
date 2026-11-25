/** Format seconds as mm:ss (negative or fractional input is clamped/floored). */
export function fmtT(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  return String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');
}

/** Up to two uppercase initials from a name. */
export function initials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
}

export const TONE_COUNT = 5;

/** Stable tone index 0..4 derived from a string. */
export function tone(key: string): number {
  let h = 0;
  for (const ch of key) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return h % TONE_COUNT;
}

/** Tailwind classes per tone (full strings so Tailwind can see them). */
export const TONE_CLASSES = [
  'bg-tone0-bg text-tone0-fg',
  'bg-tone1-bg text-tone1-fg',
  'bg-tone2-bg text-tone2-fg',
  'bg-tone3-bg text-tone3-fg',
  'bg-tone4-bg text-tone4-fg',
] as const;

export function greeting(date: Date): string {
  const h = date.getHours();
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
}

export function fmtDay(date: Date): string {
  return date.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' });
}
