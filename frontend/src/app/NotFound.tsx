import { Link } from 'react-router-dom';
import { EmptyState } from '../components/EmptyState';
import { PageHeader } from '../components/PageHeader';

export default function NotFound() {
  return (
    <>
      <PageHeader title="Page not found" />
      <EmptyState title="We could not find that page" text="The link may be old or mistyped.">
        <Link
          to="/home"
          className="inline-flex h-9 items-center rounded-control border border-accent bg-accent px-3.5 text-[0.9rem] font-semibold text-accent-ink no-underline"
        >
          Back to Home
        </Link>
      </EmptyState>
    </>
  );
}
