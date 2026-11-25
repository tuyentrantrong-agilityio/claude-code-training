import { useOutletContext } from 'react-router-dom';
import type { LayoutContext } from '../../app/Layout';
import { EmptyState } from '../../components/EmptyState';
import { PageHeader } from '../../components/PageHeader';
import { PlaceholderPage } from '../../components/PlaceholderPage';

export default function AdminPage() {
  const { role } = useOutletContext<LayoutContext>();
  if (role !== 'owner') {
    return (
      <>
        <PageHeader title="Admin" />
        <EmptyState
          title="Only owners can open this page"
          text="Use the account menu to preview as an owner."
        />
      </>
    );
  }
  return <PlaceholderPage title="Admin" />;
}
