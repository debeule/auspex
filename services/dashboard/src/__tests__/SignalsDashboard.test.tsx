import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import SignalsDashboard from '@/components/SignalsDashboard';

const directSignalFixture = {
  event_id: 'evt-001',
  source_type: 'ACADEMIC_PAPER',
  title: 'BCL11A promotes haematopoiesis',
  summary: 'Gene target study',
  confidence_score: 0.875,
  published_at: '2026-01-15T10:00:00Z',
};

const corroboratedFixture = {
  entity_key: 'BCL11A:GeneTarget',
  distinct_source_types: ['ACADEMIC_PAPER', 'PATENT'],
  corroborated_at: '2026-01-20T12:00:00Z',
  confidence: 0.92,
  participant_event_ids: ['evt-001', 'evt-002'],
};

const fullResponse = {
  ticker: 'BEAM',
  direct_signals: [directSignalFixture],
  corroborated_signals: [corroboratedFixture],
};

const emptyResponse = {
  ticker: 'BEAM',
  direct_signals: [],
  corroborated_signals: [],
};

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('SignalsDashboard', () => {
  it('test_direct_signals_table_renders_title_source_confidence_date_from_fixture', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => fullResponse,
    }));

    render(<SignalsDashboard />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'BEAM' } });
    fireEvent.submit(screen.getByRole('form'));

    await waitFor(() => {
      expect(screen.getByText('BCL11A promotes haematopoiesis')).toBeInTheDocument();
    });

    expect(screen.getAllByText('ACADEMIC_PAPER').length).toBeGreaterThan(0);
    expect(screen.getByText('87.5%')).toBeInTheDocument();
    expect(screen.getByText(/2026-01-15/)).toBeInTheDocument();
  });

  it('test_corroborated_panel_renders_entity_key_and_source_types_from_fixture', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => fullResponse,
    }));

    render(<SignalsDashboard />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'BEAM' } });
    fireEvent.submit(screen.getByRole('form'));

    await waitFor(() => {
      expect(screen.getByText('BCL11A:GeneTarget')).toBeInTheDocument();
    });

    expect(screen.getAllByText('ACADEMIC_PAPER').length).toBeGreaterThan(0);
    expect(screen.getByText('PATENT')).toBeInTheDocument();
  });

  it('test_empty_state_renders_when_both_signal_lists_are_empty', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => emptyResponse,
    }));

    render(<SignalsDashboard />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'BEAM' } });
    fireEvent.submit(screen.getByRole('form'));

    await waitFor(() => {
      expect(screen.getByText(/no signals found/i)).toBeInTheDocument();
    });

    expect(screen.queryAllByRole('row').filter(r => r.closest('tbody'))).toHaveLength(0);
  });

  it('test_api_error_renders_error_message_not_blank_page', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')));

    render(<SignalsDashboard />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'BEAM' } });
    fireEvent.submit(screen.getByRole('form'));

    await waitFor(() => {
      expect(screen.getByText(/failed to fetch signals/i)).toBeInTheDocument();
    });
  });

  it('test_ticker_input_rejects_lowercase_and_invalid_characters_before_fetch', async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);

    render(<SignalsDashboard />);

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'beam' } });
    fireEvent.submit(screen.getByRole('form'));
    expect(screen.getByText(/invalid ticker/i)).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'BEA M' } });
    fireEvent.submit(screen.getByRole('form'));
    expect(screen.getByText(/invalid ticker/i)).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
