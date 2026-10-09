import { NextResponse, type NextRequest } from 'next/server';
import { errorResponse } from '@/lib/errors';
import { SESSION_COOKIE, createSessionToken, sessionCookieOptions, verifySessionToken } from '@/lib/session';

const PUBLIC_PATHS = new Set(['/login', '/api/health', '/api/auth/login']);

/**
 * Admits only requests carrying a valid session. Pages redirect to `/login`; API routes answer 401
 * in the dashboard's error shape. A valid session is re-issued so its idle expiry restarts.
 */
export async function proxy(request: NextRequest): Promise<Response> {
  const { pathname, search } = request.nextUrl;
  if (PUBLIC_PATHS.has(pathname)) {
    return NextResponse.next();
  }

  const user = await verifySessionToken(request.cookies.get(SESSION_COOKIE)?.value);
  if (!user) {
    if (pathname.startsWith('/api/')) {
      return errorResponse(401, 'unauthenticated', 'Sign in to use the dashboard');
    }
    const login = new URL('/login', request.url);
    login.searchParams.set('next', `${pathname}${search}`);
    return NextResponse.redirect(login);
  }

  const res = NextResponse.next();
  res.cookies.set(SESSION_COOKIE, await createSessionToken(user), sessionCookieOptions(request));
  return res;
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
