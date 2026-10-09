// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import bcrypt from 'bcryptjs';
import { NextRequest } from 'next/server';
import { proxy } from '@/proxy';
import { POST as login } from '@/app/api/auth/login/route';
import { POST as logout } from '@/app/api/auth/logout/route';
import { GET as health } from '@/app/api/health/route';
import { SESSION_COOKIE, createSessionToken } from '@/lib/session';

const PASSWORD = 'correct horse battery staple';
// Cost 4 keeps the suite fast; production hashes use the script's default cost.
const PASSWORD_HASH = bcrypt.hashSync(PASSWORD, 4);

beforeEach(() => {
  vi.stubEnv('DASHBOARD_USERNAME', 'analyst');
  vi.stubEnv('DASHBOARD_PASSWORD_HASH', PASSWORD_HASH);
  vi.stubEnv('DASHBOARD_SESSION_SECRET', 'a-session-secret-of-reasonable-length-0123456789');
  vi.stubEnv('DASHBOARD_SESSION_IDLE_MINUTES', '30');
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.useRealTimers();
});

function pageRequest(path: string, cookie?: string): NextRequest {
  return new NextRequest(`http://localhost:3001${path}`, {
    headers: cookie ? { cookie: `${SESSION_COOKIE}=${cookie}` } : {},
  });
}

function loginRequest(username: string, password: string): Request {
  return new Request('http://localhost:3001/api/auth/login', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
}

function sessionCookieFrom(res: Response): string | null {
  const header = res.headers.get('set-cookie');
  if (!header) return null;
  const match = header.match(new RegExp(`${SESSION_COOKIE}=([^;]*)`));
  return match ? match[1] : null;
}

describe('single-user login', () => {
  it('test_request_without_session_is_redirected_to_login', async () => {
    const res = await proxy(pageRequest('/watchlist/SRPT'));

    expect(res.status).toBe(307);
    const location = new URL(res.headers.get('location')!);
    expect(location.pathname).toBe('/login');
    expect(location.searchParams.get('next')).toBe('/watchlist/SRPT');
  });

  it('test_api_request_without_session_returns_401', async () => {
    const res = await proxy(pageRequest('/api/core-hub/v1/watchlist'));

    expect(res.status).toBe(401);
    expect((await res.json()).error.code).toBe('unauthenticated');
  });

  it('test_health_route_is_reachable_without_session', async () => {
    const gate = await proxy(pageRequest('/api/health'));
    expect(gate.headers.get('x-middleware-next')).toBe('1');

    const res = await health();
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ status: 'ok' });
  });

  it('test_login_page_is_reachable_without_session', async () => {
    for (const path of ['/login', '/api/auth/login']) {
      const gate = await proxy(pageRequest(path));
      expect(gate.headers.get('x-middleware-next')).toBe('1');
    }
  });

  it('test_correct_credentials_set_httponly_samesite_strict_cookie', async () => {
    const res = await login(loginRequest('analyst', PASSWORD));

    expect(res.status).toBe(200);
    const header = res.headers.get('set-cookie')!;
    expect(header).toContain(`${SESSION_COOKIE}=`);
    expect(header).toMatch(/HttpOnly/i);
    expect(header).toMatch(/SameSite=Strict/i);
    expect(header).toMatch(/Path=\//);

    const gate = await proxy(pageRequest('/watchlist', sessionCookieFrom(res)!));
    expect(gate.headers.get('x-middleware-next')).toBe('1');
  });

  it('test_wrong_password_returns_401_and_sets_no_cookie', async () => {
    for (const [user, pass] of [['analyst', 'wrong'], ['someone-else', PASSWORD]]) {
      const res = await login(loginRequest(user, pass));
      expect(res.status).toBe(401);
      expect(res.headers.get('set-cookie')).toBeNull();
      expect((await res.json()).error.code).toBe('invalid_credentials');
    }
  });

  it('test_tampered_session_cookie_is_rejected', async () => {
    const token = await createSessionToken('analyst');
    const [payload, signature] = token.split('.');
    const forgedPayload = Buffer.from(
      JSON.stringify({ sub: 'analyst', exp: Date.now() + 10 * 365 * 24 * 3600 * 1000 }),
    ).toString('base64url');

    for (const cookie of [`${forgedPayload}.${signature}`, `${payload}.${signature}x`, 'garbage']) {
      const res = await proxy(pageRequest('/api/core-hub/v1/watchlist', cookie));
      expect(res.status).toBe(401);
    }

    vi.stubEnv('DASHBOARD_SESSION_SECRET', 'a-different-secret-after-rotation-0123456789');
    expect((await proxy(pageRequest('/api/core-hub/v1/watchlist', token))).status).toBe(401);
  });

  it('test_session_ends_when_the_configured_username_changes', async () => {
    const token = await createSessionToken('analyst');

    vi.stubEnv('DASHBOARD_USERNAME', 'renamed');

    expect((await proxy(pageRequest('/api/core-hub/v1/watchlist', token))).status).toBe(401);
  });

  it('test_expired_session_is_rejected', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-10-01T09:00:00Z'));
    const token = await createSessionToken('analyst');

    vi.setSystemTime(new Date('2026-10-01T09:29:00Z'));
    expect((await proxy(pageRequest('/api/core-hub/v1/watchlist', token))).headers.get('x-middleware-next')).toBe('1');

    vi.setSystemTime(new Date('2026-10-01T09:31:00Z'));
    expect((await proxy(pageRequest('/api/core-hub/v1/watchlist', token))).status).toBe(401);
  });

  it('test_activity_extends_the_idle_expiry', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-10-01T09:00:00Z'));
    const token = await createSessionToken('analyst');

    vi.setSystemTime(new Date('2026-10-01T09:20:00Z'));
    const refreshed = sessionCookieFrom(await proxy(pageRequest('/watchlist', token)));
    expect(refreshed).toBeTruthy();

    vi.setSystemTime(new Date('2026-10-01T09:45:00Z'));
    expect((await proxy(pageRequest('/watchlist', refreshed!))).headers.get('x-middleware-next')).toBe('1');
  });

  it('test_logout_clears_the_session_cookie', async () => {
    const res = await logout(new Request('http://localhost:3001/api/auth/logout', { method: 'POST' }));

    expect(res.status).toBe(204);
    const header = res.headers.get('set-cookie')!;
    expect(header).toContain(`${SESSION_COOKIE}=;`);
    expect(header).toMatch(/Max-Age=0|Expires=Thu, 01 Jan 1970/i);
  });
});
