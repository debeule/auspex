'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { WatchlistSummary, WatchlistGeneTargetStat } from '@/lib/types';

interface Props {
  ticker: string;
}

export default function CompanyDetail({ ticker }: Props) {
  const [summary, setSummary] = useState<WatchlistSummary | null>(null);
  const [geneTargets, setGeneTargets] = useState<WatchlistGeneTargetStat[]>([]);
  const [error, setError] = useState<string | null>(null);

  const base = process.env.NEXT_PUBLIC_API_URL ?? '';

  useEffect(() => {
    async function load() {
      const res = await fetch(`${base}/api/v1/watchlist/${ticker}/summary`);
      if (!res.ok) {
        setError('Failed to load summary');
        return;
      }
      const data: WatchlistSummary = await res.json();
      setSummary(data);
      setGeneTargets(data.gene_targets);
    }
    load();
  }, [ticker]);

  async function removeGeneTarget(name: string) {
    const prev = geneTargets;
    setGeneTargets(gt => gt.filter(g => g.name !== name));
    const res = await fetch(`${base}/api/v1/watchlist/${ticker}/gene-targets`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ remove: [name] }),
    });
    if (!res.ok) {
      setGeneTargets(prev);
    }
  }

  if (error) return <p>{error}</p>;
  if (!summary) return <p>Loading...</p>;

  const sortedCorroborations = [...summary.corroborations].sort(
    (a, b) => new Date(b.corroborated_at).getTime() - new Date(a.corroborated_at).getTime()
  );

  return (
    <div>
      <Link href="/watchlist">← Back to Watchlist</Link>
      <h1>{summary.ticker}</h1>
      <h2>{summary.company_name}</h2>

      <div>
        {geneTargets.map(gt => (
          <span key={gt.name}>
            <span>{gt.name}</span>
            <span>{gt.source}</span>
            <button
              aria-label={`Remove ${gt.name}`}
              onClick={() => removeGeneTarget(gt.name)}
            >
              ×
            </button>
          </span>
        ))}
      </div>

      <div>
        <div>Total signals: {summary.stats.total_direct}</div>
        <div>Corroborations: {summary.stats.total_corroborations}</div>
        {summary.stats.most_active_gene_target && (
          <div>Most active: {summary.stats.most_active_gene_target}</div>
        )}
      </div>

      <div>
        {sortedCorroborations.length === 0 ? (
          <p>No corroborations yet for these gene targets. More signals needed.</p>
        ) : (
          sortedCorroborations.map(c => (
            <div key={c.entity_key}>
              <span>{c.entity_key}</span>
              <span>{c.corroborated_at.slice(0, 10)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
