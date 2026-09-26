import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import WatchlistPage from '@/components/watchlist/WatchlistPage';
import CompanyDetail from '@/components/watchlist/CompanyDetail';

const entryFixture = [
  {
    id: 'uuid-1',
    ticker: 'SRPT',
    company_name: 'Sarepta Therapeutics',
    added_at: '2026-09-20T10:00:00Z',
    gene_targets: [{ gene_target: 'DMD', source: 'graph' }],
  },
  {
    id: 'uuid-2',
    ticker: 'BEAM',
    company_name: 'Beam Therapeutics',
    added_at: '2026-09-21T10:00:00Z',
    gene_targets: [],
  },
];

const previewFixture = {
  ticker: 'SRPT',
  company_name: 'Sarepta Therapeutics',
  graph_gene_targets: [
    { name: 'DMD', signal_count: 14 },
    { name: 'CAPN3', signal_count: 3 },
  ],
  ct_suggestions: [],
};

const summaryFixture = {
  ticker: 'SRPT',
  company_name: 'Sarepta Therapeutics',
  gene_targets: [
    { name: 'DMD', source: 'graph', signal_count: 14, last_seen: '2026-09-15T00:00:00Z' },
    { name: 'AAV9', source: 'clinicaltrials', signal_count: 0, last_seen: null },
  ],
  direct_signals: [],
  corroborations: [
    { entity_key: 'DMD | GeneTarget', corroborated_at: '2026-09-20T12:00:00Z', confidence: 0.66 },
    { entity_key: 'CAPN3 | GeneTarget', corroborated_at: '2026-09-18T12:00:00Z', confidence: 0.5 },
  ],
  stats: {
    total_direct: 47,
    total_corroborations: 2,
    most_active_gene_target: 'DMD',
    last_signal_at: '2026-09-15T14:30:00Z',
  },
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('WatchlistPage', () => {
  it('test_watchlist_page_renders_existing_entries', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => entryFixture,
    }));

    render(<WatchlistPage />);

    await waitFor(() => {
      expect(screen.getByText('SRPT')).toBeInTheDocument();
      expect(screen.getByText('BEAM')).toBeInTheDocument();
    });
  });

  it('test_lookup_calls_preview_and_renders_card', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => [] }))
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => previewFixture }))
    );

    render(<WatchlistPage />);
    await waitFor(() => {});

    fireEvent.change(screen.getByPlaceholderText(/ticker/i), { target: { value: 'SRPT' } });
    fireEvent.click(screen.getByText('Look up'));

    await waitFor(() => {
      expect(screen.getByText('Sarepta Therapeutics')).toBeInTheDocument();
      expect(screen.getByText('DMD')).toBeInTheDocument();
    });
  });

  it('test_company_name_editable_when_null', async () => {
    const nullNamePreview = { ...previewFixture, company_name: null };
    vi.stubGlobal('fetch', vi.fn()
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => [] }))
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => nullNamePreview }))
    );

    render(<WatchlistPage />);
    await waitFor(() => {});

    fireEvent.change(screen.getByPlaceholderText(/ticker/i), { target: { value: 'XYZQ' } });
    fireEvent.click(screen.getByText('Look up'));

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/company name/i)).toBeInTheDocument();
    });

    const nameInput = screen.getByPlaceholderText(/company name/i);
    fireEvent.change(nameInput, { target: { value: 'My Company' } });
    expect(nameInput).toHaveValue('My Company');
  });

  it('test_confirm_add_posts_correct_body', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => [] }))
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => previewFixture }))
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => ({
        id: 'uuid-new', ticker: 'SRPT', company_name: 'Sarepta Therapeutics',
        added_at: '2026-09-25T10:00:00Z', gene_targets: [],
      })}))
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => [] }));

    vi.stubGlobal('fetch', fetchMock);

    render(<WatchlistPage />);
    await waitFor(() => {});

    fireEvent.change(screen.getByPlaceholderText(/ticker/i), { target: { value: 'SRPT' } });
    fireEvent.click(screen.getByText('Look up'));

    await waitFor(() => {
      expect(screen.getByText('DMD')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Add to watchlist'));

    await waitFor(() => {
      const postCall = fetchMock.mock.calls.find(([url, opts]: [string, RequestInit]) =>
        url.includes('/watchlist') && opts?.method === 'POST'
      );
      expect(postCall).toBeDefined();
      const body = JSON.parse(postCall![1].body as string);
      expect(body.ticker).toBe('SRPT');
      expect(body.company_name).toBe('Sarepta Therapeutics');
      expect(body.gene_targets).toHaveLength(2);
    });
  });

  it('test_remove_requires_confirmation', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => [entryFixture[0]] }))
      .mockImplementationOnce(() => Promise.resolve({ ok: true, status: 204, json: async () => ({}) }))
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => [] }));

    vi.stubGlobal('fetch', fetchMock);

    render(<WatchlistPage />);

    await waitFor(() => {
      expect(screen.getByText('SRPT')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /remove srpt/i }));
    expect(screen.getByText(/remove srpt/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(fetchMock).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: /remove srpt/i }));
    fireEvent.click(screen.getByRole('button', { name: /confirm/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(3);
    });
  });
});

describe('CompanyDetail', () => {
  it('test_company_detail_renders_gene_target_chips', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => summaryFixture,
    }));

    render(<CompanyDetail ticker="SRPT" />);

    await waitFor(() => {
      expect(screen.getByText('DMD')).toBeInTheDocument();
      expect(screen.getByText('AAV9')).toBeInTheDocument();
    });

    expect(screen.getByText('graph')).toBeInTheDocument();
    expect(screen.getByText('clinicaltrials')).toBeInTheDocument();
  });

  it('test_company_detail_renders_corroboration_rows', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => summaryFixture,
    }));

    render(<CompanyDetail ticker="SRPT" />);

    await waitFor(() => {
      expect(screen.getByText('DMD | GeneTarget')).toBeInTheDocument();
      expect(screen.getByText('CAPN3 | GeneTarget')).toBeInTheDocument();
    });

    const rows = screen.getAllByText(/GeneTarget/);
    expect(rows[0].textContent).toContain('DMD');
  });

  it('test_gene_target_chip_remove_sends_patch', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => summaryFixture }))
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => [
        { gene_target: 'AAV9', source: 'clinicaltrials' },
      ]}));

    vi.stubGlobal('fetch', fetchMock);

    render(<CompanyDetail ticker="SRPT" />);

    await waitFor(() => {
      expect(screen.getByText('DMD')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /remove dmd/i }));

    await waitFor(() => {
      const patchCall = fetchMock.mock.calls.find(([url, opts]: [string, RequestInit]) =>
        url.includes('/gene-targets') && opts?.method === 'PATCH'
      );
      expect(patchCall).toBeDefined();
      const body = JSON.parse(patchCall![1].body as string);
      expect(body.remove).toEqual(['DMD']);
    });
  });
});
