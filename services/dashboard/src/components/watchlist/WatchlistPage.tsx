'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api, errorMessage } from '@/lib/api';
import { formatUtc, isValidTicker } from '@/lib/ticker';
import { WatchlistEntry, WatchlistGeneTarget, WatchlistPreview } from '@/lib/types';
import Button from '../ui/Button';
import Card from '../ui/Card';
import ConfirmDialog from '../ui/ConfirmDialog';
import FormField from '../ui/FormField';
import Table from '../ui/Table';
import { EmptyState, ErrorMessage, Loading } from '../ui/Status';

function previewTargets(preview: WatchlistPreview): WatchlistGeneTarget[] {
  return [
    ...preview.graph_gene_targets.map((g) => ({ gene_target: g.name, source: 'graph' as const })),
    ...preview.ct_suggestions.map((s) => ({ gene_target: s.term, source: 'clinicaltrials' as const })),
  ];
}

export default function WatchlistPage() {
  const [entries, setEntries] = useState<WatchlistEntry[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [tickerInput, setTickerInput] = useState('');
  const [preview, setPreview] = useState<WatchlistPreview | null>(null);
  const [lookingUp, setLookingUp] = useState(false);
  const [adding, setAdding] = useState(false);
  const [companyNameOverride, setCompanyNameOverride] = useState('');
  const [selectedTargets, setSelectedTargets] = useState<WatchlistGeneTarget[]>([]);
  const [confirmRemoveTicker, setConfirmRemoveTicker] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  async function fetchEntries() {
    try {
      setEntries(await api.watchlist.list());
      setListError(null);
    } catch (err) {
      setListError(errorMessage(err));
    }
  }

  useEffect(() => {
    let cancelled = false;
    api.watchlist
      .list()
      .then((items) => {
        if (!cancelled) setEntries(items);
      })
      .catch((err) => {
        if (!cancelled) setListError(errorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleLookup() {
    setValidationError(null);
    setActionError(null);
    if (!isValidTicker(tickerInput)) {
      setValidationError('Invalid ticker — must match ^[A-Z][A-Z0-9.\\-]{0,9}$');
      return;
    }
    setLookingUp(true);
    try {
      const data = await api.watchlist.preview(tickerInput);
      setPreview(data);
      setCompanyNameOverride(data.company_name ?? '');
      setSelectedTargets(previewTargets(data));
    } catch (err) {
      setActionError(`Lookup failed: ${errorMessage(err)}`);
    } finally {
      setLookingUp(false);
    }
  }

  function toggleTarget(gt: WatchlistGeneTarget) {
    setSelectedTargets((prev) =>
      prev.some((t) => t.gene_target === gt.gene_target)
        ? prev.filter((t) => t.gene_target !== gt.gene_target)
        : [...prev, gt],
    );
  }

  async function handleAdd() {
    if (!preview) return;
    setActionError(null);
    setAdding(true);
    try {
      await api.watchlist.add({
        ticker: preview.ticker,
        company_name: companyNameOverride || preview.company_name,
        gene_targets: selectedTargets,
      });
      setPreview(null);
      setTickerInput('');
      await fetchEntries();
    } catch (err) {
      setActionError(errorMessage(err));
    } finally {
      setAdding(false);
    }
  }

  async function handleRemoveConfirm() {
    const ticker = confirmRemoveTicker;
    if (!ticker) return;
    setConfirmRemoveTicker(null);
    setActionError(null);
    try {
      await api.watchlist.remove(ticker);
      await fetchEntries();
    } catch (err) {
      setActionError(`Could not remove ${ticker}: ${errorMessage(err)}`);
    }
  }

  return (
    <div className="space-y-6">
      <Card title="Add a company">
        <div className="flex items-end gap-2">
          <FormField
            id="watchlist-ticker"
            label="Ticker"
            type="text"
            value={tickerInput}
            onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
            placeholder="Enter ticker (e.g. SRPT)"
          />
          <Button onClick={handleLookup} disabled={lookingUp}>
            Look up
          </Button>
        </div>
        {validationError && <ErrorMessage>{validationError}</ErrorMessage>}
        {lookingUp && <Loading>Looking up {tickerInput}…</Loading>}

        {preview && (
          <div className="space-y-3">
            {preview.company_name ? (
              <p className="font-medium">{preview.company_name}</p>
            ) : (
              <FormField
                id="watchlist-company-name"
                label="Company name"
                type="text"
                value={companyNameOverride}
                onChange={(e) => setCompanyNameOverride(e.target.value)}
                placeholder="Enter company name"
              />
            )}

            <div className="flex flex-wrap gap-2">
              {previewTargets(preview).map((gt) => {
                const selected = selectedTargets.some((t) => t.gene_target === gt.gene_target);
                return (
                  <button
                    key={gt.gene_target}
                    type="button"
                    onClick={() => toggleTarget(gt)}
                    aria-pressed={selected}
                    className={`rounded-full border px-2 py-0.5 text-xs ${
                      selected ? 'border-blue-600 bg-blue-50 text-blue-800' : 'border-gray-300 text-gray-600'
                    }`}
                  >
                    {gt.gene_target}
                  </button>
                );
              })}
            </div>

            <Button onClick={handleAdd} disabled={adding}>
              Add to watchlist
            </Button>
          </div>
        )}
      </Card>

      {actionError && <ErrorMessage>{actionError}</ErrorMessage>}

      <Card title="Tracked companies">
        {listError && <ErrorMessage>{listError}</ErrorMessage>}
        {!listError && entries === null && <Loading>Loading watchlist…</Loading>}
        {entries !== null && entries.length === 0 && (
          <EmptyState>No companies on the watchlist yet.</EmptyState>
        )}
        {entries !== null && entries.length > 0 && (
          <Table caption="Watchlist" headers={['Ticker', 'Company', 'Added', '']}>
            {entries.map((entry) => (
              <tr key={entry.ticker}>
                <td className="px-2 py-1.5">
                  <Link href={`/watchlist/${entry.ticker}`} className="text-blue-700 hover:underline">
                    {entry.ticker}
                  </Link>
                </td>
                <td className="px-2 py-1.5">{entry.company_name}</td>
                <td className="px-2 py-1.5 whitespace-nowrap">{formatUtc(entry.added_at)}</td>
                <td className="px-2 py-1.5 text-right">
                  <Button
                    variant="secondary"
                    aria-label={`Remove ${entry.ticker}`}
                    onClick={() => setConfirmRemoveTicker(entry.ticker)}
                  >
                    ×
                  </Button>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      {confirmRemoveTicker && (
        <ConfirmDialog
          title={`Remove ${confirmRemoveTicker}?`}
          onConfirm={handleRemoveConfirm}
          onCancel={() => setConfirmRemoveTicker(null)}
        >
          Its gene targets are removed with it. Historical signals are preserved.
        </ConfirmDialog>
      )}
    </div>
  );
}
