import { NextResponse } from 'next/server';
import { credentialsAreValid, loginIsConfigured } from '@/lib/credentials';
import { errorResponse } from '@/lib/errors';
import { SESSION_COOKIE, createSessionToken, sessionCookieOptions } from '@/lib/session';

export const dynamic = 'force-dynamic';

export async function POST(request: Request): Promise<Response> {
  if (!loginIsConfigured()) {
    return errorResponse(503, 'not_configured', 'Dashboard login is not configured; see SETUP.md');
  }
  let username: unknown;
  let password: unknown;
  try {
    ({ username, password } = await request.json());
  } catch {
    return errorResponse(400, 'bad_request', 'Expected a JSON body with username and password');
  }
  if (typeof username !== 'string' || typeof password !== 'string') {
    return errorResponse(400, 'bad_request', 'Expected a JSON body with username and password');
  }
  if (!(await credentialsAreValid(username, password))) {
    return errorResponse(401, 'invalid_credentials', 'Wrong username or password');
  }

  const res = NextResponse.json({ username });
  res.cookies.set(SESSION_COOKIE, await createSessionToken(username), sessionCookieOptions(request));
  return res;
}
