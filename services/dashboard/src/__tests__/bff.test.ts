// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DELETE, GET, PATCH, POST } from '@/app/api/[service]/[...path]/route';

function params(service: string, path: string[]) {
  return { params: Promise.resolve({ service, path }) };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

beforeEach(() => {
  vi.stubEnv('CORE_HUB_URL', 'http://core-hub.internal:8080');
  vi.stubEnv('CORE_HUB_WRITE_TOKEN', 'write-token-under-test');
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe('backend-for-frontend', () => {
  it('test_bff_forwards_get_to_core_hub_using_server_side_url', async () => {
    const upstream = vi.fn().mockImplementation(async () => jsonResponse({ ticker: 'BEAM' }));
    vi.stubGlobal('fetch', upstream);

    const res = await GET(
      new Request('http://dashboard.local/api/core-hub/v1/signals/BEAM?limit=5'),
      params('core-hub', ['v1', 'signals', 'BEAM']),
    );

    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ticker: 'BEAM' });
    expect(upstream.mock.calls[0][0]).toBe('http://core-hub.internal:8080/api/v1/signals/BEAM?limit=5');

    // Read per request, not baked in at build time.
    vi.stubEnv('CORE_HUB_URL', 'http://elsewhere:9090');
    await GET(
      new Request('http://dashboard.local/api/core-hub/v1/watchlist'),
      params('core-hub', ['v1', 'watchlist']),
    );
    expect(upstream.mock.calls[1][0]).toBe('http://elsewhere:9090/api/v1/watchlist');
  });

  it('test_bff_adds_write_token_on_non_get_requests_only', async () => {
    const upstream = vi.fn().mockImplementation(async () => jsonResponse([]));
    vi.stubGlobal('fetch', upstream);

    await GET(
      new Request('http://dashboard.local/api/core-hub/v1/watchlist', {
        headers: { cookie: 'auspex_session=abc', authorization: 'Bearer from-browser' },
      }),
      params('core-hub', ['v1', 'watchlist']),
    );
    await POST(
      new Request('http://dashboard.local/api/core-hub/v1/watchlist', {
        method: 'POST',
        headers: { 'content-type': 'application/json', cookie: 'auspex_session=abc' },
        body: JSON.stringify({ ticker: 'SRPT' }),
      }),
      params('core-hub', ['v1', 'watchlist']),
    );
    await PATCH(
      new Request('http://dashboard.local/api/core-hub/v1/watchlist/SRPT/gene-targets', {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ add: ['DMD'] }),
      }),
      params('core-hub', ['v1', 'watchlist', 'SRPT', 'gene-targets']),
    );
    await DELETE(
      new Request('http://dashboard.local/api/core-hub/v1/watchlist/SRPT', { method: 'DELETE' }),
      params('core-hub', ['v1', 'watchlist', 'SRPT']),
    );

    const headersOf = (i: number) => new Headers((upstream.mock.calls[i][1] as RequestInit).headers);
    expect(headersOf(0).get('authorization')).toBeNull();
    expect(headersOf(0).get('cookie')).toBeNull();
    for (const i of [1, 2, 3]) {
      expect(headersOf(i).get('authorization')).toBe('Bearer write-token-under-test');
      expect(headersOf(i).get('cookie')).toBeNull();
    }
    const post = upstream.mock.calls[1][1] as RequestInit;
    expect(post.method).toBe('POST');
    expect(new TextDecoder().decode(post.body as ArrayBuffer)).toBe('{"ticker":"SRPT"}');
    expect(headersOf(1).get('content-type')).toBe('application/json');
  });

  it('test_bff_normalises_upstream_error_into_error_shape_with_upstream_status', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn()
        .mockResolvedValueOnce(jsonResponse({ message: 'Ticker already in watchlist: SRPT', status: 409 }, 409))
        .mockResolvedValueOnce(new Response('boom', { status: 500 })),
    );

    const conflict = await POST(
      new Request('http://dashboard.local/api/core-hub/v1/watchlist', { method: 'POST', body: '{}' }),
      params('core-hub', ['v1', 'watchlist']),
    );
    expect(conflict.status).toBe(409);
    expect(await conflict.json()).toEqual({
      error: { code: 'conflict', message: 'Ticker already in watchlist: SRPT', upstream_status: 409 },
    });

    const failure = await GET(
      new Request('http://dashboard.local/api/core-hub/v1/watchlist'),
      params('core-hub', ['v1', 'watchlist']),
    );
    expect(failure.status).toBe(502);
    const body = await failure.json();
    expect(body.error.code).toBe('upstream_error');
    expect(body.error.upstream_status).toBe(500);
    expect(typeof body.error.message).toBe('string');
  });

  it('test_bff_returns_502_with_error_shape_when_upstream_is_unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('fetch failed')));

    const res = await GET(
      new Request('http://dashboard.local/api/core-hub/v1/watchlist'),
      params('core-hub', ['v1', 'watchlist']),
    );

    expect(res.status).toBe(502);
    const body = await res.json();
    expect(body.error.code).toBe('upstream_unreachable');
    expect(body.error.upstream_status).toBeNull();
    expect(body.error.message).toMatch(/core-hub/);
  });

  it('test_bff_wraps_list_responses_into_items_and_next_cursor', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse([{ ticker: 'SRPT' }])));

    const res = await GET(
      new Request('http://dashboard.local/api/core-hub/v1/watchlist'),
      params('core-hub', ['v1', 'watchlist']),
    );

    expect(await res.json()).toEqual({ items: [{ ticker: 'SRPT' }], next_cursor: null });
  });

  it('test_bff_passes_no_content_through', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })));

    const res = await DELETE(
      new Request('http://dashboard.local/api/core-hub/v1/watchlist/SRPT', { method: 'DELETE' }),
      params('core-hub', ['v1', 'watchlist', 'SRPT']),
    );

    expect(res.status).toBe(204);
  });

  it('test_bff_rejects_unknown_service_without_calling_upstream', async () => {
    const upstream = vi.fn();
    vi.stubGlobal('fetch', upstream);

    const res = await GET(
      new Request('http://dashboard.local/api/postgres/anything'),
      params('postgres', ['anything']),
    );

    expect(res.status).toBe(404);
    expect((await res.json()).error.code).toBe('not_found');
    expect(upstream).not.toHaveBeenCalled();
  });
});
