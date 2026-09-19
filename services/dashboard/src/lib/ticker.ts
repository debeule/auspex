export const TICKER_REGEX = /^[A-Z][A-Z0-9.\-]{0,9}$/;

export function isValidTicker(ticker: string): boolean {
  return TICKER_REGEX.test(ticker);
}

export function formatConfidence(score: number): string {
  return `${(score * 100).toFixed(1)}%`;
}

export function formatDate(iso: string): string {
  return iso.slice(0, 10);
}
