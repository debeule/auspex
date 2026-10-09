import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import LoginForm from '@/components/LoginForm';

const navigate = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: navigate, refresh: vi.fn() }),
  usePathname: () => '/',
}));

function submit(username: string, password: string) {
  fireEvent.change(screen.getByLabelText(/username/i), { target: { value: username } });
  fireEvent.change(screen.getByLabelText(/password/i), { target: { value: password } });
  fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
}

beforeEach(() => {
  vi.restoreAllMocks();
  navigate.mockReset();
});

describe('LoginForm', () => {
  it('test_sign_in_posts_credentials_and_returns_to_the_requested_page', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ username: 'analyst' }) });
    vi.stubGlobal('fetch', fetchMock);

    render(<LoginForm next="/watchlist/SRPT" />);
    submit('analyst', 'secret');

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/watchlist/SRPT'));
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/auth/login');
    expect(JSON.parse(init.body as string)).toEqual({ username: 'analyst', password: 'secret' });
  });

  it('test_sign_in_ignores_a_next_target_on_another_origin', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) }));

    render(<LoginForm next="//evil.example/steal" />);
    submit('analyst', 'secret');

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/'));
  });

  it('test_wrong_credentials_show_the_error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ error: { code: 'invalid_credentials', message: 'Wrong username or password', upstream_status: null } }),
    }));

    render(<LoginForm next="/" />);
    submit('analyst', 'nope');

    expect(await screen.findByRole('alert')).toHaveTextContent('Wrong username or password');
    expect(navigate).not.toHaveBeenCalled();
  });
});
