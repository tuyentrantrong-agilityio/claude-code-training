import { EmptyState } from './EmptyState';
import { PageHeader } from './PageHeader';

/** Stand-in for screens that arrive in later work items. */
export function PlaceholderPage({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <>
      <PageHeader title={title} subtitle={subtitle} />
      <EmptyState title="Coming soon" text="This screen comes in a later work item." />
    </>
  );
}
