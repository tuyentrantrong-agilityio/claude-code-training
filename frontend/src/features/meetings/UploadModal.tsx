import { useRef, useState, type DragEvent, type FormEvent } from 'react';
import { Modal } from '../../components/Modal';
import { ApiError } from '../../lib/api';
import { ACCEPT, fmtSize, stripExtension, validateFile } from './upload-validation';
import { uploadMeeting, type Language, type MeetingSummary } from './api';

const field =
  'h-[38px] rounded-control border border-line bg-surface px-3 text-ink disabled:opacity-60';

interface UploadModalProps {
  onClose: () => void;
  onUploaded: (meeting: MeetingSummary) => void;
}

export function UploadModal({ onClose, onUploaded }: UploadModalProps) {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [language, setLanguage] = useState<Language>('en');
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);

  const uploading = progress !== null;

  const choose = (picked: File | undefined) => {
    if (!picked) return;
    const problem = validateFile(picked);
    setError(problem);
    if (problem) {
      setFile(null);
      return;
    }
    setFile(picked);
    setTitle(stripExtension(picked.name));
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (!uploading) choose(e.dataTransfer.files[0]);
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!file || uploading) return;
    setError(null);
    setProgress(0);
    try {
      const meeting = await uploadMeeting(
        { file, language, title: title.trim() || undefined },
        (f) => setProgress(f),
      );
      onUploaded(meeting);
    } catch (err) {
      setProgress(null);
      setError(
        err instanceof ApiError || err instanceof Error ? err.message : 'Something went wrong',
      );
    }
  };

  const percent = Math.round((progress ?? 0) * 100);

  return (
    <Modal title="Upload a recording" onClose={uploading ? () => undefined : onClose}>
      <form onSubmit={(e) => void onSubmit(e)} className="flex flex-col gap-3.5">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`flex flex-col items-center gap-1 rounded-[14px] border-[1.5px] border-dashed px-4 py-7 text-center ${
            dragging ? 'border-accent bg-accent-soft' : 'border-line bg-sunken'
          }`}
        >
          <button
            type="button"
            disabled={uploading}
            onClick={() => input.current?.click()}
            className="cursor-pointer border-0 bg-transparent p-0 font-semibold text-ink disabled:cursor-default"
          >
            Drop an audio or video file here
          </button>
          <span className="text-[0.85rem] text-muted">
            or click to choose a file (up to 500 MB)
          </span>
          {file && (
            <span className="mt-1.5 text-[0.9rem]">
              <b>{file.name}</b> <span className="text-muted">({fmtSize(file.size)})</span>
            </span>
          )}
          <input
            ref={input}
            type="file"
            accept={ACCEPT}
            aria-label="Recording file"
            className="hidden"
            onChange={(e) => {
              choose(e.target.files?.[0]);
              e.target.value = '';
            }}
          />
        </div>

        <label className="flex flex-col gap-1 text-[0.85rem] font-semibold">
          Title
          <input
            type="text"
            value={title}
            disabled={uploading}
            onChange={(e) => setTitle(e.target.value)}
            className={`${field} font-normal`}
          />
        </label>

        <label className="flex flex-col gap-1 text-[0.85rem] font-semibold">
          Language
          <select
            value={language}
            disabled={uploading}
            onChange={(e) => setLanguage(e.target.value as Language)}
            className={`${field} font-normal`}
          >
            <option value="en">English</option>
            <option value="vi">Vietnamese</option>
          </select>
        </label>

        {uploading && (
          <div
            role="progressbar"
            aria-label="Upload progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent}
            className="h-2 overflow-hidden rounded-full bg-sunken"
          >
            <div className="h-full bg-accent" style={{ width: `${percent}%` }} />
          </div>
        )}

        {error && (
          <p role="alert" className="text-[0.88rem] text-bad">
            {error}
          </p>
        )}

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={!file || uploading}
            className="h-[38px] cursor-pointer rounded-control border-0 bg-accent px-4 font-semibold text-accent-ink disabled:cursor-default disabled:opacity-50"
          >
            {uploading ? 'Uploading' : 'Start processing'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
