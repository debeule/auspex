// @vitest-environment node
import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '@/lib/api';

const SRC = path.resolve(__dirname, '..');

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) {
      return name === '__tests__' || full === path.join(SRC, 'app', 'api') ? [] : sourceFiles(full);
    }
    return /\.(ts|tsx)$/.test(name) ? [full] : [];
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('typed API client', () => {
  it('test_components_call_only_same_origin_api_paths', async () => {
    // Browser code reaches the backend only through the client, and the client never names a host.
    const clientCode = sourceFiles(SRC).filter(
      (f) => !f.startsWith(path.join(SRC, 'lib', 'bff')) && f !== path.join(SRC, 'proxy.ts'),
    );
    expect(clientCode.length).toBeGreaterThan(5);
    for (const file of clientCode) {
      const code = readFileSync(file, 'utf8');
      const rel = path.relative(SRC, file);
      expect(code, rel).not.toMatch(/NEXT_PUBLIC_/);
      expect(code, rel).not.toMatch(/https?:\/\//);
      if (rel !== path.join('lib', 'api.ts')) {
        expect(code, `${rel} calls fetch directly`).not.toMatch(/\bfetch\(/);
      }
    }

    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      const empty = init?.method === 'DELETE';
      return new Response(empty ? null : JSON.stringify({ items: [], next_cursor: null }), {
        status: empty ? 204 : 200,
        headers: { 'content-type': 'application/json' },
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    await api.signals.forTicker('BEAM');
    await api.watchlist.list();
    await api.watchlist.preview('SRPT');
    await api.watchlist.add({ ticker: 'SRPT', company_name: 'Sarepta', gene_targets: [] });
    await api.watchlist.remove('SRPT');
    await api.watchlist.patchGeneTargets('SRPT', { add: ['DMD'] });
    await api.watchlist.summary('SRPT');

    expect(fetchMock).toHaveBeenCalledTimes(7);
    for (const [url] of fetchMock.mock.calls) {
      expect(url).toMatch(/^\/api\/core-hub\/v1\//);
    }
  });

  it('test_client_raises_the_bff_error_message', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ error: { code: 'conflict', message: 'Ticker already in watchlist: SRPT', upstream_status: 409 } }),
          { status: 409 },
        ),
      ),
    );

    await expect(api.watchlist.add({ ticker: 'SRPT', company_name: 'Sarepta', gene_targets: [] }))
      .rejects.toMatchObject({ message: 'Ticker already in watchlist: SRPT', status: 409, code: 'conflict' });
  });
});
