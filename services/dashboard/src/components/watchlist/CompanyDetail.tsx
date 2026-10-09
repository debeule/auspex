'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api, errorMessage } from '@/lib/api';
import { formatConfidence, formatUtc } from '@/lib/ticker';
import { WatchlistGeneTarget, WatchlistGeneTargetStat, WatchlistSummary } from '@/lib/types';
import DirectSignalsTable from '../DirectSignalsTable';
import Button from '../ui/Button';
import Card from '../ui/Card';
import FormField from '../ui/FormField';
import Table from '../ui/Table';
import { EmptyState, ErrorMessage, Loading } from '../ui/Status';

interface Props {
  ticker: string;
}

/** Keeps the counts already known for each target; targets new to the list start at zero. */
function mergeTargets(
  current: WatchlistGeneTargetStat[],
  saved: WatchlistGeneTarget[],
): WatchlistGeneTargetStat[] {
  return saved.map(
    (t) =>
      current.find((c) => c.name === t.gene_target) ?? {
        name: t.gene_target,
        source: t.source,
        signal_count: 0,
        last_seen: null,
      },
  );
}

export default function CompanyDetail({ ticker }: Props) {
  const [summary, setSummary] = useState<WatchlistSummary | null>(null);
  const [geneTargets, setGeneTargets] = useState<WatchlistGeneTargetStat[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [newTarget, setNewTarget] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.watchlist
      .summary(ticker)
      .then((data) => {
        if (cancelled) return;
        setSummary(data);
        setGeneTargets(data.gene_targets);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(`Failed to load ${ticker}: ${errorMessage(err)}`);
      });
    return () => {
      cancelled = true;
    };
  }, [ticker]);

  async function removeGeneTarget(name: string) {
    const prev = geneTargets;
    setActionError(null);
    setGeneTargets((gt) => gt.filter((g) => g.name !== name));
    try {
      await api.watchlist.patchGeneTargets(ticker, { remove: [name] });
    } catch (err) {
      setGeneTargets(prev);
      setActionError(`Could not remove ${name}: ${errorMessage(err)}`);
    }
  }

  async function addGeneTarget(e: React.FormEvent) {
    e.preventDefault();
    const name = newTarget.trim().toUpperCase();
    if (!name) return;
    setActionError(null);
    setSaving(true);
    try {
      const saved = await api.watchlist.patchGeneTargets(ticker, { add: [name] });
      setGeneTargets((current) => mergeTargets(current, saved));
      setNewTarget('');
    } catch (err) {
      setActionError(`Could not add ${name}: ${errorMessage(err)}`);
    } finally {
      setSaving(false);
    }
  }

  if (loadError) return <ErrorMessage>{loadError}</ErrorMessage>;
  if (!summary) return <Loading>Loading {ticker}…</Loading>;

  const sortedCorroborations = [...summary.corroborations].sort(
    (a, b) => new Date(b.corroborated_at).getTime() - new Date(a.corroborated_at).getTime(),
  );

  return (
    <div className="space-y-6">
      <Link href="/watchlist" className="text-sm text-blue-700 hover:underline">
        ← Back to Watchlist
      </Link>
      <div>
        <h1 className="text-2xl font-semibold">{summary.ticker}</h1>
        <h2 className="text-gray-600">{summary.company_name}</h2>
      </div>

      {actionError && <ErrorMessage>{actionError}</ErrorMessage>}

      <Card title="Gene targets">
        {geneTargets.length === 0 && <EmptyState>No gene targets tracked.</EmptyState>}
        <ul className="flex flex-wrap gap-2">
          {geneTargets.map((gt) => (
            <li key={gt.name} className="flex items-center gap-1 rounded-full border border-gray-300 px-2 py-0.5 text-xs">
              <span className="font-medium">{gt.name}</span>
              <span className="text-gray-500">{gt.source}</span>
              <button
                type="button"
                aria-label={`Remove ${gt.name}`}
                onClick={() => removeGeneTarget(gt.name)}
                className="ml-1 text-gray-500 hover:text-red-600"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
        <form onSubmit={addGeneTarget} className="flex items-end gap-2">
          <FormField
            id="gene-target-add"
            label="Add gene target"
            type="text"
            value={newTarget}
            onChange={(e) => setNewTarget(e.target.value)}
            placeholder="e.g. SGCB"
          />
          <Button type="submit" disabled={saving}>
            Add
          </Button>
        </form>
      </Card>

      <Card title="Activity">
        <ul className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
          <li>Total signals: {summary.stats.total_direct}</li>
          <li>Corroborations: {summary.stats.total_corroborations}</li>
          {summary.stats.most_active_gene_target && (
            <li>Most active: {summary.stats.most_active_gene_target}</li>
          )}
          {summary.stats.last_signal_at && <li>Last signal: {formatUtc(summary.stats.last_signal_at)}</li>}
        </ul>
      </Card>

      <Card title="Direct signals">
        {summary.direct_signals.length === 0 ? (
          <EmptyState>No signals mention {summary.ticker} yet.</EmptyState>
        ) : (
          <DirectSignalsTable signals={summary.direct_signals} />
        )}
      </Card>

      <Card title="Corroborations">
        {sortedCorroborations.length === 0 ? (
          <EmptyState>No corroborations yet for these gene targets. More signals needed.</EmptyState>
        ) : (
          <Table caption="Corroborations" headers={['Entity', 'Confidence', 'Corroborated']}>
            {sortedCorroborations.map((c) => (
              <tr key={c.entity_key}>
                <td className="px-2 py-1.5">{c.entity_key}</td>
                <td className="px-2 py-1.5">{formatConfidence(c.confidence)}</td>
                <td className="px-2 py-1.5 whitespace-nowrap">{formatUtc(c.corroborated_at)}</td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
