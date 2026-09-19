'use client';

import { useState } from 'react';
import { isValidTicker } from '@/lib/ticker';
import { TickerSignalsResponse } from '@/lib/types';
import DirectSignalsTable from './DirectSignalsTable';
import CorroboratedPanel from './CorroboratedPanel';

export default function SignalsDashboard() {
  const [ticker, setTicker] = useState('');
  const [data, setData] = useState<TickerSignalsResponse | null>(null);
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

    const base = process.env.NEXT_PUBLIC_API_URL ?? '';
    try {
      const res = await fetch(`${base}/api/v1/signals/${ticker}`);
      if (!res.ok) {
        setError(`Failed to fetch signals — server returned ${res.status}`);
        return;
      }
      setData(await res.json());
    } catch {
      setError('Failed to fetch signals — network error');
    }
  }

  const isEmpty =
    data !== null &&
    data.direct_signals.length === 0 &&
    data.corroborated_signals.length === 0;

  return (
    <div>
      <form role="form" onSubmit={handleSubmit}>
        <input
          type="text"
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="Enter ticker (e.g. BEAM)"
        />
        <button type="submit">Search</button>
      </form>

      {validationError && <p>{validationError}</p>}
      {error && <p>{error}</p>}

      {isEmpty && <p>No signals found for {data!.ticker}</p>}

      {data && !isEmpty && (
        <>
          <DirectSignalsTable signals={data.direct_signals} />
          <CorroboratedPanel signals={data.corroborated_signals} />
        </>
      )}
    </div>
  );
}
