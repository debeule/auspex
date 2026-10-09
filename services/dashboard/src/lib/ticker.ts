export const TICKER_REGEX = /^[A-Z][A-Z0-9.\-]{0,9}$/;

export function isValidTicker(ticker: string): boolean {
  return TICKER_REGEX.test(ticker);
}

export function formatConfidence(score: number): string {
  return `${(score * 100).toFixed(1)}%`;
}

/** An API timestamp as `YYYY-MM-DD HH:MM UTC`, whatever the viewer's time zone. */
export function formatUtc(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return `${date.toISOString().slice(0, 16).replace('T', ' ')} UTC`;
}
