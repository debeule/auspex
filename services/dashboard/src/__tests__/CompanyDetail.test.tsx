import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CompanyDetail from '@/components/watchlist/CompanyDetail';

const summaryFixture = {
  ticker: 'SRPT',
  company_name: 'Sarepta Therapeutics',
  gene_targets: [
    { name: 'DMD', source: 'graph', signal_count: 14, last_seen: '2026-09-15T00:00:00Z' },
  ],
  direct_signals: [
    {
      event_id: 'evt-101',
      source_type: 'sec_8k',
      title: 'Sarepta reports ELEVIDYS label expansion',
      summary: '8-K item 8.01',
      confidence_score: 0.91,
      published_at: '2026-09-15T14:30:00Z',
    },
    {
      event_id: 'evt-102',
      source_type: 'clinicaltrials',
      title: 'Phase 3 LGMD2E trial posted',
      summary: 'New study record',
      confidence_score: 0.7,
      published_at: '2026-09-01T08:00:00Z',
    },
  ],
  corroborations: [],
  stats: {
    total_direct: 2,
    total_corroborations: 0,
    most_active_gene_target: 'DMD',
    last_signal_at: '2026-09-15T14:30:00Z',
  },
};

function ok(body: unknown) {
  return Promise.resolve({ ok: true, status: 200, json: async () => body });
}

const noSignals = { ticker: 'SRPT', direct_signals: [], corroborated_signals: [], context_corroborations: [] };

/** Answers the signals request the page makes for its context list; `rest` answers the others. */
function withSignals(rest: (url: string, init?: RequestInit) => unknown, signals: unknown = noSignals) {
  return vi.fn((url: string, init?: RequestInit) =>
    url.includes('/v1/signals/') ? ok(signals) : rest(url, init),
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('CompanyDetail', () => {
  it('test_company_detail_lists_direct_signals', async () => {
    vi.stubGlobal('fetch', withSignals(vi.fn().mockImplementation(() => ok(summaryFixture))));

    render(<CompanyDetail ticker="SRPT" />);

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    const table = await screen.findByRole('table', { name: /direct signals/i });
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent('Sarepta reports ELEVIDYS label expansion');
    expect(rows[0]).toHaveTextContent('sec_8k');
    expect(rows[0]).toHaveTextContent('91.0%');
    expect(rows[0]).toHaveTextContent('2026-09-15 14:30 UTC');
    expect(rows[1]).toHaveTextContent('Phase 3 LGMD2E trial posted');
  });

  it('test_company_detail_shows_empty_signals_state', async () => {
    vi.stubGlobal('fetch', withSignals(vi.fn().mockImplementation(() => ok({ ...summaryFixture, direct_signals: [] }))));

    render(<CompanyDetail ticker="SRPT" />);

    expect(await screen.findByText(/no signals mention srpt yet/i)).toBeInTheDocument();
  });

  it('test_gene_target_can_be_added', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => ok(summaryFixture))
      .mockImplementationOnce(() => ok({
        items: [
          { gene_target: 'DMD', source: 'graph' },
          { gene_target: 'SGCB', source: 'manual' },
        ],
        next_cursor: null,
      }));
    vi.stubGlobal('fetch', withSignals(fetchMock));

    render(<CompanyDetail ticker="SRPT" />);
    await screen.findByText('DMD');

    fireEvent.change(screen.getByLabelText(/add gene target/i), { target: { value: 'sgcb' } });
    fireEvent.click(screen.getByRole('button', { name: /^add$/i }));

    expect(await screen.findByText('SGCB')).toBeInTheDocument();
    expect(screen.getByText('manual')).toBeInTheDocument();
    expect(screen.getByText('DMD')).toBeInTheDocument();

    const [url, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(url).toBe('/api/core-hub/v1/watchlist/SRPT/gene-targets');
    expect(init.method).toBe('PATCH');
    expect(JSON.parse(init.body as string)).toEqual({ add: ['SGCB'] });
    expect(screen.getByLabelText(/add gene target/i)).toHaveValue('');
  });

  it('test_failed_gene_target_change_shows_the_error', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => ok(summaryFixture))
      .mockImplementationOnce(() => Promise.resolve({
        ok: false,
        status: 404,
        json: async () => ({ error: { code: 'not_found', message: 'Ticker not in watchlist: SRPT', upstream_status: 404 } }),
      }));
    vi.stubGlobal('fetch', withSignals(fetchMock));

    render(<CompanyDetail ticker="SRPT" />);
    await screen.findByText('DMD');

    fireEvent.click(screen.getByRole('button', { name: /remove dmd/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Ticker not in watchlist: SRPT');
    await waitFor(() => expect(screen.getByText('DMD')).toBeInTheDocument());
  });

  it('lists context corroborations with their reason', async () => {
    const signals = {
      ...noSignals,
      context_corroborations: [
        {
          entity_key: 'gene therapy:Mechanism',
          reason: 'broad_entity',
          distinct_source_types: ['biorxiv', 'edgar'],
          episode_opened_at: '2026-09-10T00:00:00Z',
          corroborated_at: '2026-09-12T00:00:00Z',
          participant_event_ids: ['evt-101', 'evt-201'],
        },
        {
          entity_key: 'DMD:GeneTarget',
          reason: 'no_independent_pair_for_ticker',
          distinct_source_types: ['clinicaltrials', 'pubmed'],
          episode_opened_at: '2026-09-01T00:00:00Z',
          corroborated_at: '2026-09-01T00:00:00Z',
          participant_event_ids: ['evt-102', 'evt-301'],
        },
      ],
    };
    vi.stubGlobal('fetch', withSignals(vi.fn().mockImplementation(() => ok(summaryFixture)), signals));

    render(<CompanyDetail ticker="SRPT" />);

    const table = await screen.findByRole('table', { name: /context corroborations/i });
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent('gene therapy:Mechanism');
    expect(rows[0]).toHaveTextContent('Broad entity');
    expect(rows[1]).toHaveTextContent('DMD:GeneTarget');
    expect(rows[1]).toHaveTextContent('No independent pair for this ticker');
  });
});
