import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '../App';

describe('Layout', () => {
  it('renders the home heading and the four nav links', () => {
    render(
      <MemoryRouter initialEntries={['/home']}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { level: 1, name: 'Home' })).toBeInTheDocument();
    const nav = screen.getByRole('navigation');
    for (const name of ['Home', 'Meetings', 'Ask', 'Follow-ups']) {
      expect(screen.getByRole('link', { name })).toBeInTheDocument();
    }
    expect(nav.querySelectorAll('a')).toHaveLength(4);
  });
});
