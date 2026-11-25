export const MAX_UPLOAD_BYTES = 500 * 1024 * 1024;
const EXTENSIONS = ['.mp3', '.m4a', '.wav', '.mp4', '.webm', '.ogg', '.mov'];
export const ACCEPT = ['audio/*', 'video/*', ...EXTENSIONS].join(',');

export const MSG_UNSUPPORTED = 'Unsupported file type. Use an audio or video file.';
export const MSG_TOO_LARGE = 'File is too large. The limit is 500 MB.';

export function validateFile(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!EXTENSIONS.some((ext) => name.endsWith(ext))) return MSG_UNSUPPORTED;
  if (file.size > MAX_UPLOAD_BYTES) return MSG_TOO_LARGE;
  return null;
}

export function fmtSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function stripExtension(name: string): string {
  const dot = name.lastIndexOf('.');
  return dot > 0 ? name.slice(0, dot) : name;
}
