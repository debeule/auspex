import { NextResponse } from 'next/server';
import { SESSION_COOKIE, sessionCookieOptions } from '@/lib/session';

export const dynamic = 'force-dynamic';

export function POST(request: Request): Response {
  const res = new NextResponse(null, { status: 204 });
  res.cookies.set(SESSION_COOKIE, '', { ...sessionCookieOptions(request), maxAge: 0 });
  return res;
}
