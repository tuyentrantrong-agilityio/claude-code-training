import { useParams } from 'react-router-dom';
import { PlaceholderPage } from '../../components/PlaceholderPage';

export default function MeetingPage() {
  const { id } = useParams();
  return <PlaceholderPage title="Meeting" subtitle={id ? `Meeting ${id}` : undefined} />;
}
