import { errorResponse } from './errors';

interface Upstream {
  /** Env var holding the service's base URL, read on every request so the image is not tied to one stack. */
  urlEnv: string;
  /** Prefix the forwarded path is mounted under on the upstream. */
  basePath: string;
  /** Env var holding a bearer token sent on writes, for services that require one. */
  writeTokenEnv?: string;
}

const UPSTREAMS: Record<string, Upstream> = {
  'core-hub': { urlEnv: 'CORE_HUB_URL', basePath: '/api', writeTokenEnv: 'CORE_HUB_WRITE_TOKEN' },
  scraper: { urlEnv: 'SCRAPER_API_URL', basePath: '' },
  prices: { urlEnv: 'PRICE_API_URL', basePath: '' },
};

const READ_METHODS = new Set(['GET', 'HEAD']);
const FORWARDED_HEADERS = ['accept', 'content-type'];
const UPSTREAM_TIMEOUT_MS = 30_000;

const STATUS_CODES: Record<number, string> = {
  400: 'bad_request',
  401: 'unauthorized',
  403: 'forbidden',
  404: 'not_found',
  409: 'conflict',
  422: 'unprocessable',
  429: 'rate_limited',
};

/**
 * Forwards a browser request to a backend service and returns its answer in the dashboard's
 * shapes: errors as {@link ErrorBody}, JSON arrays as `{items, next_cursor}`. Holds no business
 * logic; the browser's cookies and credentials never reach the upstream.
 */
export async function forward(service: string, path: string[], request: Request): Promise<Response> {
  const upstream = UPSTREAMS[service];
  if (!upstream) {
    return errorResponse(404, 'not_found', `Unknown service: ${service}`);
  }
  const baseUrl = process.env[upstream.urlEnv];
  if (!baseUrl) {
    return errorResponse(503, 'not_configured', `${upstream.urlEnv} is not set`);
  }

  const search = new URL(request.url).search;
  const target = `${baseUrl.replace(/\/$/, '')}${upstream.basePath}/${path.map(encodeURIComponent).join('/')}${search}`;

  const headers = new Headers();
  for (const name of FORWARDED_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const isWrite = !READ_METHODS.has(request.method);
  if (isWrite && upstream.writeTokenEnv) {
    headers.set('authorization', `Bearer ${process.env[upstream.writeTokenEnv] ?? ''}`);
  }

  let res: Response;
  try {
    res = await fetch(target, {
      method: request.method,
      headers,
      body: isWrite ? await request.arrayBuffer() : undefined,
      cache: 'no-store',
      redirect: 'manual',
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
    });
  } catch (err) {
    const reason = err instanceof Error ? err.message : String(err);
    return errorResponse(502, 'upstream_unreachable', `${service} is unreachable: ${reason}`);
  }

  if (!res.ok) {
    return upstreamError(service, res);
  }
  if (res.status === 204 || request.method === 'HEAD') {
    return new Response(null, { status: res.status });
  }

  const contentType = res.headers.get('content-type') ?? '';
  if (!contentType.includes('application/json')) {
    return new Response(res.body, { status: res.status, headers: { 'content-type': contentType } });
  }
  const body: unknown = await res.json();
  return Response.json(Array.isArray(body) ? { items: body, next_cursor: null } : body, {
    status: res.status,
  });
}

async function upstreamError(service: string, res: Response): Promise<Response> {
  let message = `${service} returned ${res.status}`;
  try {
    const body = (await res.json()) as { message?: unknown; error?: unknown };
    const detail = body.message ?? body.error;
    if (typeof detail === 'string' && detail) message = detail;
  } catch {
    // Non-JSON error bodies keep the generic message.
  }
  // A failing upstream is a bad gateway from the browser's point of view; client errors pass through.
  const status = res.status >= 500 ? 502 : res.status;
  const code = res.status >= 500 ? 'upstream_error' : (STATUS_CODES[res.status] ?? 'upstream_error');
  return errorResponse(status, code, message, res.status);
}
