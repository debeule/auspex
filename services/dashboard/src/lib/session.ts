/**
 * Signed session tokens for the single dashboard user: `base64url(payload).base64url(hmac)`,
 * HMAC-SHA256 over the payload with `DASHBOARD_SESSION_SECRET`. The payload carries the idle
 * expiry; every authenticated request re-issues the token, so the session ends after
 * `DASHBOARD_SESSION_IDLE_MINUTES` without activity.
 */

export const SESSION_COOKIE = 'auspex_session';

const DEFAULT_IDLE_MINUTES = 30;
const encoder = new TextEncoder();

interface SessionPayload {
  sub: string;
  /** Idle expiry, epoch milliseconds. */
  exp: number;
}

export function idleMinutes(): number {
  const parsed = Number(process.env.DASHBOARD_SESSION_IDLE_MINUTES);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_IDLE_MINUTES;
}

async function signingKey(): Promise<CryptoKey | null> {
  const secret = process.env.DASHBOARD_SESSION_SECRET;
  if (!secret) return null;
  return crypto.subtle.importKey('raw', encoder.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, [
    'sign',
    'verify',
  ]);
}

function toBase64Url(bytes: Uint8Array): string {
  return Buffer.from(bytes).toString('base64url');
}

function fromBase64Url(text: string): Uint8Array<ArrayBuffer> | null {
  if (!/^[A-Za-z0-9_-]+$/.test(text)) return null;
  return new Uint8Array(Buffer.from(text, 'base64url'));
}

export async function createSessionToken(username: string): Promise<string> {
  const key = await signingKey();
  if (!key) throw new Error('DASHBOARD_SESSION_SECRET is not set');
  const payload: SessionPayload = { sub: username, exp: Date.now() + idleMinutes() * 60_000 };
  const encoded = toBase64Url(encoder.encode(JSON.stringify(payload)));
  const signature = new Uint8Array(await crypto.subtle.sign('HMAC', key, encoder.encode(encoded)));
  return `${encoded}.${toBase64Url(signature)}`;
}

/** The session's user, or null when the token is missing, forged, signed with another secret, or idle too long. */
export async function verifySessionToken(token: string | undefined): Promise<string | null> {
  if (!token) return null;
  const key = await signingKey();
  if (!key) return null;
  const parts = token.split('.');
  if (parts.length !== 2) return null;
  const [encoded, signatureText] = parts;
  const signature = fromBase64Url(signatureText);
  if (!signature) return null;
  const valid = await crypto.subtle.verify('HMAC', key, signature, encoder.encode(encoded));
  if (!valid) return null;

  try {
    const payload = JSON.parse(Buffer.from(encoded, 'base64url').toString('utf8')) as SessionPayload;
    if (typeof payload.sub !== 'string' || typeof payload.exp !== 'number') return null;
    if (payload.exp <= Date.now()) return null;
    if (payload.sub !== process.env.DASHBOARD_USERNAME) return null;
    return payload.sub;
  } catch {
    return null;
  }
}

/** Cookie attributes for the session; `Secure` only when the request itself arrived over HTTPS. */
export function sessionCookieOptions(request: Request) {
  const forwardedProto = request.headers.get('x-forwarded-proto');
  const secure = (forwardedProto ?? new URL(request.url).protocol.replace(':', '')) === 'https';
  return {
    httpOnly: true,
    sameSite: 'strict' as const,
    secure,
    path: '/',
    maxAge: idleMinutes() * 60,
  };
}
