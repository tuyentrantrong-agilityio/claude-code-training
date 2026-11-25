import type { ReactNode } from 'react';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  children?: ReactNode;
}

export function PageHeader({ title, subtitle, children }: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-start gap-3">
      <div className="flex min-w-0 flex-col gap-[3px]">
        <h1 className="text-[1.65rem]">{title}</h1>
        {subtitle && <p className="text-muted">{subtitle}</p>}
      </div>
      <span className="flex-1" />
      {children && <div className="flex flex-wrap items-center gap-2.5">{children}</div>}
    </div>
  );
}
