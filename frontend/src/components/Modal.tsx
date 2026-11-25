import { useEffect, useId, type ReactNode } from 'react';

interface ModalProps {
  title: string;
  onClose: () => void;
  children?: ReactNode;
}

export function Modal({ title, onClose, children }: ModalProps) {
  const titleId = useId();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div
      data-testid="modal-backdrop"
      className="fixed inset-0 z-[60] grid place-items-center bg-[rgb(15_15_30/0.5)] p-4"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="flex max-h-[92vh] w-full max-w-[500px] flex-col gap-3.5 overflow-auto rounded-[18px] bg-surface p-[22px] shadow-pop"
      >
        <div className="flex items-center justify-between gap-2.5">
          <h2 id={titleId} className="text-[1.1rem]">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="h-[30px] cursor-pointer rounded-control border border-transparent bg-transparent px-[11px] text-[0.82rem] font-semibold text-muted hover:bg-sunken hover:text-ink"
          >
            Close
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
