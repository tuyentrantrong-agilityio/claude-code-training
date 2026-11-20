import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './app/Layout';
import AskPage from './features/ask/AskPage';
import FollowUpsPage from './features/follow-ups/FollowUpsPage';
import HomePage from './features/home/HomePage';
import MeetingsPage from './features/meetings/MeetingsPage';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/home" replace />} />
        <Route path="/home" element={<HomePage />} />
        <Route path="/meetings" element={<MeetingsPage />} />
        <Route path="/ask" element={<AskPage />} />
        <Route path="/follow-ups" element={<FollowUpsPage />} />
      </Route>
    </Routes>
  );
}
