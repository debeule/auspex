import type {
  TickerSignalsResponse,
  WatchlistEntry,
  WatchlistGeneTarget,
  WatchlistPreview,
  WatchlistSummary,
} from './types';

/** Every backend call goes through the dashboard's own origin; the server forwards it. */
const CORE_HUB = '/api/core-hub';

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

interface ListResponse<T> {
  items: T[];
  next_cursor: string | null;
}

export interface WatchlistAddBody {
  ticker: string;
  company_name: string | null;
  gene_targets: WatchlistGeneTarget[];
}

export interface GeneTargetPatch {
  add?: string[];
  remove?: string[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
    });
  } catch {
    throw new ApiError('The dashboard server could not be reached', 0, 'network_error');
  }
  if (!res.ok) {
    let message = `Request failed with status ${res.status}`;
    let code = 'unknown';
    try {
      const body = await res.json();
      message = body?.error?.message ?? message;
      code = body?.error?.code ?? code;
    } catch {
      // Keep the status-based message.
    }
    throw new ApiError(message, res.status, code);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

const enc = encodeURIComponent;

function coreHub<T>(path: string, init?: RequestInit): Promise<T> {
  return request<T>(`${CORE_HUB}${path}`, init);
}

/** Typed client for the backend, as exposed through the dashboard's server layer. */
export const api = {
  auth: {
    login: (username: string, password: string) =>
      request<{ username: string }>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      }),
    logout: () => request<void>('/api/auth/logout', { method: 'POST' }),
  },
  signals: {
    forTicker: (ticker: string) => coreHub<TickerSignalsResponse>(`/v1/signals/${enc(ticker)}`),
  },
  watchlist: {
    list: async () => (await coreHub<ListResponse<WatchlistEntry>>('/v1/watchlist')).items,
    preview: (ticker: string) =>
      coreHub<WatchlistPreview>(`/v1/watchlist/preview?ticker=${enc(ticker)}`),
    add: (body: WatchlistAddBody) =>
      coreHub<WatchlistEntry>('/v1/watchlist', { method: 'POST', body: JSON.stringify(body) }),
    remove: (ticker: string) =>
      coreHub<void>(`/v1/watchlist/${enc(ticker)}`, { method: 'DELETE' }),
    patchGeneTargets: async (ticker: string, patch: GeneTargetPatch) =>
      (
        await coreHub<ListResponse<WatchlistGeneTarget>>(`/v1/watchlist/${enc(ticker)}/gene-targets`, {
          method: 'PATCH',
          body: JSON.stringify(patch),
        })
      ).items,
    summary: (ticker: string) => coreHub<WatchlistSummary>(`/v1/watchlist/${enc(ticker)}/summary`),
  },
};

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
