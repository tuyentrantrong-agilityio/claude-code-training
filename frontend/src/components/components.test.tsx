import { act, render, screen, fireEvent } from '@testing-library/react';
import { useState } from 'react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { Avatar } from './Avatar';
import { AvatarStack } from './AvatarStack';
import { EmptyState } from './EmptyState';
import { Modal } from './Modal';
import { PageHeader } from './PageHeader';
import { Switch } from './Switch';
import { TimeStamp } from './TimeStamp';
import { ToastProvider } from './Toast';
import { useToast } from './toast-context';

describe('Modal', () => {
  it('closes on Escape, on backdrop mousedown, and on the Close button', () => {
    const onClose = vi.fn();
    render(
      <Modal title="Upload" onClose={onClose}>
        <p>Body</p>
      </Modal>,
    );
    expect(screen.getByRole('dialog', { name: 'Upload' })).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.mouseDown(screen.getByTestId('modal-backdrop'));
    expect(onClose).toHaveBeenCalledTimes(2);

    fireEvent.mouseDown(screen.getByText('Body'));
    expect(onClose).toHaveBeenCalledTimes(2);

    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalledTimes(3);
  });
});

describe('Switch', () => {
  it('toggles aria-checked', () => {
    function Demo() {
      const [on, setOn] = useState(false);
      return <Switch checked={on} onChange={setOn} label="Auto-join" />;
    }
    render(<Demo />);
    const sw = screen.getByRole('switch', { name: 'Auto-join' });
    expect(sw).toHaveAttribute('aria-checked', 'false');
    fireEvent.click(sw);
    expect(sw).toHaveAttribute('aria-checked', 'true');
    fireEvent.click(sw);
    expect(sw).toHaveAttribute('aria-checked', 'false');
  });
});

describe('useToast', () => {
  it('shows the message then removes it after about 2.5s', () => {
    vi.useFakeTimers();
    try {
      function Button() {
        const toast = useToast();
        return <button onClick={() => toast('Saved')}>go</button>;
      }
      render(
        <ToastProvider>
          <Button />
        </ToastProvider>,
      );
      act(() => {
        screen.getByText('go').click();
      });
      expect(screen.getByText('Saved')).toBeInTheDocument();
      act(() => {
        vi.advanceTimersByTime(2400);
      });
      expect(screen.getByText('Saved')).toBeInTheDocument();
      act(() => {
        vi.advanceTimersByTime(200);
      });
      expect(screen.queryByText('Saved')).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('TimeStamp', () => {
  it('formats mm:ss and navigates to the meeting with ?t=', () => {
    function Where() {
      const loc = useLocation();
      return <p data-testid="loc">{loc.pathname + loc.search}</p>;
    }
    render(
      <MemoryRouter initialEntries={['/home']}>
        <TimeStamp meetingId="m1" at={612} />
        <Routes>
          <Route path="*" element={<Where />} />
        </Routes>
      </MemoryRouter>,
    );
    const btn = screen.getByRole('button', { name: 'Jump to 10:12' });
    expect(btn).toHaveTextContent('10:12');
    fireEvent.click(btn);
    expect(screen.getByTestId('loc')).toHaveTextContent('/meetings/m1?t=612');
  });
});

describe('Avatar, AvatarStack, PageHeader, EmptyState', () => {
  it('Avatar shows initials', () => {
    render(<Avatar name="Maya Chen" />);
    expect(screen.getByTestId('avatar')).toHaveTextContent('MC');
  });

  it('AvatarStack shows 4 avatars then +N', () => {
    render(<AvatarStack names={['A One', 'B Two', 'C Three', 'D Four', 'E Five', 'F Six']} />);
    expect(screen.getAllByTestId('avatar')).toHaveLength(4);
    expect(screen.getByText('+2')).toBeInTheDocument();
  });

  it('AvatarStack shows no +N at or below the max', () => {
    render(<AvatarStack names={['A One', 'B Two', 'C Three', 'D Four']} />);
    expect(screen.queryByText(/^\+/)).not.toBeInTheDocument();
  });

  it('PageHeader renders title, subtitle and actions', () => {
    render(
      <PageHeader title="Meetings" subtitle="Every recorded meeting">
        <button>Upload</button>
      </PageHeader>,
    );
    expect(screen.getByRole('heading', { level: 1, name: 'Meetings' })).toBeInTheDocument();
    expect(screen.getByText('Every recorded meeting')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Upload' })).toBeInTheDocument();
  });

  it('EmptyState renders title, text and children', () => {
    render(
      <EmptyState title="Nothing here" text="Start somewhere.">
        <a href="/x">Go</a>
      </EmptyState>,
    );
    expect(screen.getByRole('heading', { name: 'Nothing here' })).toBeInTheDocument();
    expect(screen.getByText('Start somewhere.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Go' })).toBeInTheDocument();
  });
});
