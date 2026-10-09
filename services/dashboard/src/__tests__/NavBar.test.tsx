import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import NavBar from '@/components/NavBar';

const navigate = vi.fn();
let pathname = '/watchlist';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: navigate, refresh: vi.fn() }),
  usePathname: () => pathname,
}));

beforeEach(() => {
  vi.restoreAllMocks();
  navigate.mockReset();
  pathname = '/watchlist';
});

describe('NavBar', () => {
  it('test_sign_out_ends_the_session_and_goes_to_login', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 204, json: async () => ({}) });
    vi.stubGlobal('fetch', fetchMock);

    render(<NavBar />);
    expect(screen.getByRole('link', { name: 'Watchlist' })).toHaveAttribute('aria-current', 'page');
    fireEvent.click(screen.getByRole('button', { name: /sign out/i }));

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/login'));
    expect(fetchMock.mock.calls[0][0]).toBe('/api/auth/logout');
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('POST');
  });

  it('test_login_page_shows_no_navigation', () => {
    pathname = '/login';
    const { container } = render(<NavBar />);
    expect(container).toBeEmptyDOMElement();
  });
});
