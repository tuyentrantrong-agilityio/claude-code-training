import type { ReactNode } from 'react';

interface EmptyStateProps {
  title: string;
  text: string;
  children?: ReactNode;
}

export function EmptyState({ title, text, children }: EmptyStateProps) {
  return (
    <div className="rounded-[18px] border-[1.5px] border-dashed border-line bg-surface px-5 py-11 text-center">
      <svg
        className="mx-auto mb-3.5 block"
        width="120"
        height="80"
        viewBox="0 0 120 80"
        aria-hidden="true"
      >
        <rect x="6" y="8" width="30" height="64" rx="9" fill="var(--color-accent-soft)" />
        <rect x="45" y="8" width="30" height="42" rx="9" fill="var(--color-accent-line)" />
        <rect x="84" y="8" width="30" height="54" rx="9" fill="var(--color-accent-soft)" />
      </svg>
      <h2 className="text-[1.1rem]">{title}</h2>
      <p className="mx-auto mt-1.5 mb-3.5 max-w-[48ch] text-muted">{text}</p>
      {children}
    </div>
  );
}
