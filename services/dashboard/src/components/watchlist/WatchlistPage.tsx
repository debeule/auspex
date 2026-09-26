'use client';

import { useState, useEffect } from 'react';
import { isValidTicker } from '@/lib/ticker';
import { WatchlistEntry, WatchlistPreview, WatchlistGeneTarget } from '@/lib/types';

export default function WatchlistPage() {
  const [entries, setEntries] = useState<WatchlistEntry[]>([]);
  const [tickerInput, setTickerInput] = useState('');
  const [preview, setPreview] = useState<WatchlistPreview | null>(null);
  const [companyNameOverride, setCompanyNameOverride] = useState('');
  const [selectedTargets, setSelectedTargets] = useState<WatchlistGeneTarget[]>([]);
  const [confirmRemoveTicker, setConfirmRemoveTicker] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const base = process.env.NEXT_PUBLIC_API_URL ?? '';

  useEffect(() => {
    fetchEntries();
  }, []);

  async function fetchEntries() {
    const res = await fetch(`${base}/api/v1/watchlist`);
    if (res.ok) setEntries(await res.json());
  }

  async function handleLookup() {
    setValidationError(null);
    if (!isValidTicker(tickerInput)) {
      setValidationError('Invalid ticker — must match ^[A-Z][A-Z0-9.\\-]{0,9}$');
      return;
    }
    const res = await fetch(`${base}/api/v1/watchlist/preview?ticker=${tickerInput}`);
    if (!res.ok) return;
    const data: WatchlistPreview = await res.json();
    setPreview(data);
    setCompanyNameOverride(data.company_name ?? '');
    const targets: WatchlistGeneTarget[] = [
      ...data.graph_gene_targets.map(g => ({ gene_target: g.name, source: 'graph' as const })),
      ...data.ct_suggestions.map(s => ({ gene_target: s.term, source: 'clinicaltrials' as const })),
    ];
    setSelectedTargets(targets);
  }

  function toggleTarget(gt: WatchlistGeneTarget) {
    setSelectedTargets(prev => {
      const exists = prev.find(t => t.gene_target === gt.gene_target);
      return exists
        ? prev.filter(t => t.gene_target !== gt.gene_target)
        : [...prev, gt];
    });
  }

  async function handleAdd() {
    if (!preview) return;
    const res = await fetch(`${base}/api/v1/watchlist`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ticker: preview.ticker,
        company_name: companyNameOverride || preview.company_name,
        gene_targets: selectedTargets,
      }),
    });
    if (res.ok) {
      setPreview(null);
      setTickerInput('');
      await fetchEntries();
    }
  }

  async function handleRemoveConfirm() {
    if (!confirmRemoveTicker) return;
    await fetch(`${base}/api/v1/watchlist/${confirmRemoveTicker}`, { method: 'DELETE' });
    setConfirmRemoveTicker(null);
    await fetchEntries();
  }

  const allChips = preview
    ? [
        ...preview.graph_gene_targets.map(g => ({ gene_target: g.name, source: 'graph' as const })),
        ...preview.ct_suggestions.map(s => ({ gene_target: s.term, source: 'clinicaltrials' as const })),
      ]
    : [];

  return (
    <div>
      <h1>Watchlist</h1>

      <div>
        <input
          type="text"
          value={tickerInput}
          onChange={e => setTickerInput(e.target.value.toUpperCase())}
          placeholder="Enter ticker (e.g. SRPT)"
        />
        <button onClick={handleLookup}>Look up</button>
        {validationError && <p>{validationError}</p>}
      </div>

      {preview && (
        <div>
          {preview.company_name ? (
            <p>{preview.company_name}</p>
          ) : (
            <input
              type="text"
              value={companyNameOverride}
              onChange={e => setCompanyNameOverride(e.target.value)}
              placeholder="Enter company name"
            />
          )}

          <div>
            {allChips.map(gt => {
              const selected = !!selectedTargets.find(t => t.gene_target === gt.gene_target);
              return (
                <button
                  key={gt.gene_target}
                  onClick={() => toggleTarget(gt)}
                  aria-pressed={selected}
                >
                  {gt.gene_target}
                </button>
              );
            })}
          </div>

          <button onClick={handleAdd}>Add to watchlist</button>
        </div>
      )}

      {entries.map(entry => (
        <div key={entry.ticker}>
          <a href={`/watchlist/${entry.ticker}`}>{entry.ticker}</a>
          <span>{entry.company_name}</span>
          <button
            aria-label={`Remove ${entry.ticker}`}
            onClick={() => setConfirmRemoveTicker(entry.ticker)}
          >
            ×
          </button>
        </div>
      ))}

      {confirmRemoveTicker && (
        <div role="dialog">
          <p>
            Remove {confirmRemoveTicker} and its gene targets from the watchlist? Historical signals
            are preserved.
          </p>
          <button onClick={() => setConfirmRemoveTicker(null)}>Cancel</button>
          <button onClick={handleRemoveConfirm}>Confirm</button>
        </div>
      )}
    </div>
  );
}
