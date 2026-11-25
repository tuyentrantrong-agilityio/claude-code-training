import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './app/Layout';
import RequireAuth from './app/RequireAuth';
import { SessionProvider } from './app/SessionProvider';
import NotFound from './app/NotFound';
import { ToastProvider } from './components/Toast';
import AdminPage from './features/admin/AdminPage';
import SignInPage from './features/auth/SignInPage';
import AskPage from './features/ask/AskPage';
import CalendarPage from './features/calendar/CalendarPage';
import ConnectionsPage from './features/connections/ConnectionsPage';
import DesktopPage from './features/desktop/DesktopPage';
import FollowUpsPage from './features/follow-ups/FollowUpsPage';
import FoldersPage from './features/folders/FoldersPage';
import HomePage from './features/home/HomePage';
import LivePage from './features/live/LivePage';
import MeetingPage from './features/meetings/MeetingPage';
import MeetingsPage from './features/meetings/MeetingsPage';
import WeekPage from './features/week/WeekPage';

export default function App() {
  return (
    <SessionProvider>
      <ToastProvider>
        <Routes>
          <Route path="/sign-in" element={<SignInPage />} />
          <Route element={<RequireAuth />}>
            <Route element={<Layout />}>
              <Route index element={<Navigate to="/home" replace />} />
              <Route path="/home" element={<HomePage />} />
              <Route path="/meetings" element={<MeetingsPage />} />
              <Route path="/meetings/:id" element={<MeetingPage />} />
              <Route path="/ask" element={<AskPage />} />
              <Route path="/live" element={<LivePage />} />
              <Route path="/follow-ups" element={<FollowUpsPage />} />
              <Route path="/week" element={<WeekPage />} />
              <Route path="/folders" element={<FoldersPage />} />
              <Route path="/calendar" element={<CalendarPage />} />
              <Route path="/connections" element={<ConnectionsPage />} />
              <Route path="/desktop" element={<DesktopPage />} />
              <Route path="/admin" element={<AdminPage />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Route>
        </Routes>
      </ToastProvider>
    </SessionProvider>
  );
}
