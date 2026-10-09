'use client';

import { useState } from 'react';
import { api, errorMessage } from '@/lib/api';
import { isValidTicker } from '@/lib/ticker';
import { TickerSignalsResponse } from '@/lib/types';
import DirectSignalsTable from './DirectSignalsTable';
import CorroboratedPanel from './CorroboratedPanel';
import Button from './ui/Button';
import Card from './ui/Card';
import { EmptyState, ErrorMessage, Loading } from './ui/Status';

export default function SignalsDashboard() {
  const [ticker, setTicker] = useState('');
  const [data, setData] = useState<TickerSignalsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setValidationError(null);
    setError(null);
    setData(null);

    if (!isValidTicker(ticker)) {
      setValidationError('Invalid ticker — must match ^[A-Z][A-Z0-9.\\-]{0,9}$');
      return;
    }

    setLoading(true);
    try {
      setData(await api.signals.forTicker(ticker));
    } catch (err) {
      setError(`Failed to fetch signals: ${errorMessage(err)}`);
    } finally {
      setLoading(false);
    }
  }

  const isEmpty =
    data !== null && data.direct_signals.length === 0 && data.corroborated_signals.length === 0;

  return (
    <div className="space-y-4">
      <form role="form" onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          aria-label="Ticker"
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="Enter ticker (e.g. BEAM)"
          className="rounded border border-gray-300 px-2 py-1.5 text-sm"
        />
        <Button type="submit">Search</Button>
      </form>

      {validationError && <ErrorMessage>{validationError}</ErrorMessage>}
      {error && <ErrorMessage>{error}</ErrorMessage>}
      {loading && <Loading>Loading signals…</Loading>}

      {isEmpty && <EmptyState>No signals found for {data.ticker}</EmptyState>}

      {data && !isEmpty && (
        <>
          <Card title="Direct signals">
            <DirectSignalsTable signals={data.direct_signals} />
          </Card>
          <Card title="Corroborated">
            <CorroboratedPanel signals={data.corroborated_signals} />
          </Card>
        </>
      )}
    </div>
  );
}
