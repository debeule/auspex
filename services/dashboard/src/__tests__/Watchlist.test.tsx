import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
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

function listOf<T>(items: T[]) {
  return { items, next_cursor: null };
}

function errorOf(status: number, code: string, message: string) {
  return {
    ok: false,
    status,
    json: async () => ({ error: { code, message, upstream_status: status } }),
  };
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('WatchlistPage', () => {
  it('test_watchlist_page_renders_existing_entries', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => listOf(entryFixture),
    }));

    render(<WatchlistPage />);

    await waitFor(() => {
      expect(screen.getByText('SRPT')).toBeInTheDocument();
      expect(screen.getByText('BEAM')).toBeInTheDocument();
    });
  });

  it('test_lookup_calls_preview_and_renders_card', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => listOf([]) }))
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
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => listOf([]) }))
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
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => listOf([]) }))
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => previewFixture }))
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => ({
        id: 'uuid-new', ticker: 'SRPT', company_name: 'Sarepta Therapeutics',
        added_at: '2026-09-25T10:00:00Z', gene_targets: [],
      })}))
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => listOf([]) }));

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
      const postCall = fetchMock.mock.calls.find((call) => {
        const [url, opts] = call as [string, RequestInit];
        return url.includes('/watchlist') && opts?.method === 'POST';
      });
      expect(postCall).toBeDefined();
      const body = JSON.parse(postCall![1].body as string);
      expect(body.ticker).toBe('SRPT');
      expect(body.company_name).toBe('Sarepta Therapeutics');
      expect(body.gene_targets).toHaveLength(2);
    });
  });

  it('test_remove_requires_confirmation', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => listOf([entryFixture[0]]) }))
      .mockImplementationOnce(() => Promise.resolve({ ok: true, status: 204, json: async () => ({}) }))
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => listOf([]) }));

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

  it('test_failed_add_shows_the_error_message', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => listOf([]) }))
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => previewFixture }))
      .mockImplementationOnce(() => Promise.resolve(errorOf(409, 'conflict', 'Ticker already in watchlist: SRPT')))
    );

    render(<WatchlistPage />);
    await screen.findByText(/no companies on the watchlist/i);

    fireEvent.change(screen.getByPlaceholderText(/ticker/i), { target: { value: 'SRPT' } });
    fireEvent.click(screen.getByText('Look up'));
    await screen.findByText('CAPN3');

    fireEvent.click(screen.getByText('Add to watchlist'));

    expect(await screen.findByRole('alert')).toHaveTextContent('Ticker already in watchlist: SRPT');
    expect(screen.getByText('Add to watchlist')).toBeInTheDocument();
  });

  it('test_failed_remove_keeps_the_entry_and_shows_the_error', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => listOf([entryFixture[0]]) }))
      .mockImplementationOnce(() => Promise.resolve(errorOf(502, 'upstream_unreachable', 'core-hub is unreachable')));
    vi.stubGlobal('fetch', fetchMock);

    render(<WatchlistPage />);
    await screen.findByText('SRPT');

    fireEvent.click(screen.getByRole('button', { name: /remove srpt/i }));
    fireEvent.click(screen.getByRole('button', { name: /confirm/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('core-hub is unreachable');
    expect(screen.getByText('SRPT')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('test_list_shows_loading_then_entries', async () => {
    let resolveList: (value: unknown) => void = () => {};
    vi.stubGlobal('fetch', vi.fn().mockImplementationOnce(
      () => new Promise((resolve) => { resolveList = resolve; }),
    ));

    render(<WatchlistPage />);
    expect(screen.getByText(/loading watchlist/i)).toBeInTheDocument();
    expect(screen.queryByText('SRPT')).not.toBeInTheDocument();

    resolveList({ ok: true, json: async () => listOf(entryFixture) });

    expect(await screen.findByText('SRPT')).toBeInTheDocument();
    expect(screen.queryByText(/loading watchlist/i)).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'SRPT' })).toHaveAttribute('href', '/watchlist/SRPT');
    expect(screen.getByText('2026-09-20 10:00 UTC')).toBeInTheDocument();
  });

  it('test_empty_and_failed_list_states_are_shown', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => listOf([]) })));
    const { unmount } = render(<WatchlistPage />);
    expect(await screen.findByText(/no companies on the watchlist/i)).toBeInTheDocument();
    unmount();

    vi.stubGlobal('fetch', vi.fn()
      .mockImplementationOnce(() => Promise.resolve(errorOf(502, 'upstream_unreachable', 'core-hub is unreachable'))));
    render(<WatchlistPage />);
    expect(await screen.findByRole('alert')).toHaveTextContent('core-hub is unreachable');
  });

  it('test_confirm_dialog_is_modal_and_closes_on_escape', async () => {
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => listOf([entryFixture[0]]) }));
    vi.stubGlobal('fetch', fetchMock);

    render(<WatchlistPage />);
    await screen.findByText('SRPT');

    const opener = screen.getByRole('button', { name: /remove srpt/i });
    opener.focus();
    fireEvent.click(opener);

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAccessibleName(/remove srpt/i);

    const cancel = within(dialog).getByRole('button', { name: /cancel/i });
    const confirm = within(dialog).getByRole('button', { name: /confirm/i });
    expect(cancel).toHaveFocus();

    // Focus is trapped: Tab from the last control wraps to the first, Shift+Tab wraps back.
    confirm.focus();
    fireEvent.keyDown(dialog, { key: 'Tab' });
    expect(cancel).toHaveFocus();
    fireEvent.keyDown(dialog, { key: 'Tab', shiftKey: true });
    expect(confirm).toHaveFocus();

    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
    expect(fetchMock).toHaveBeenCalledTimes(1);
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
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: async () => listOf([
        { gene_target: 'AAV9', source: 'clinicaltrials' },
      ])}));

    vi.stubGlobal('fetch', fetchMock);

    render(<CompanyDetail ticker="SRPT" />);

    await waitFor(() => {
      expect(screen.getByText('DMD')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /remove dmd/i }));

    await waitFor(() => {
      const patchCall = fetchMock.mock.calls.find((call) => {
        const [url, opts] = call as [string, RequestInit];
        return url.includes('/gene-targets') && opts?.method === 'PATCH';
      });
      expect(patchCall).toBeDefined();
      const body = JSON.parse(patchCall![1].body as string);
      expect(body.remove).toEqual(['DMD']);
    });
  });
});
