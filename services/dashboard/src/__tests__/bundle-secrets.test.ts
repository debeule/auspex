// @vitest-environment node
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * Runs against the output of `next build`, built with the same environment this test sees, so a
 * secret inlined into a client chunk shows up here by value as well as by name.
 */
const STATIC_DIR = path.resolve(__dirname, '../../.next/static');

const SERVER_ONLY_ENV = [
  'DASHBOARD_PASSWORD_HASH',
  'DASHBOARD_SESSION_SECRET',
  'CORE_HUB_WRITE_TOKEN',
  'CORE_HUB_URL',
  'SCRAPER_URL',
  'PRICE_SERVICE_URL',
];

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    return statSync(full).isDirectory() ? files(full) : [full];
  });
}

describe('client bundle', () => {
  it('test_no_server_secret_appears_in_client_bundle', () => {
    expect(existsSync(STATIC_DIR), 'run `npm run build` first').toBe(true);
    const bundle = files(STATIC_DIR).filter((f) => /\.(js|css|json|html)$/.test(f));
    expect(bundle.length).toBeGreaterThan(0);

    for (const name of SERVER_ONLY_ENV) {
      const value = process.env[name];
      expect(value, `${name} must be set for the build and this test`).toBeTruthy();
    }

    for (const file of bundle) {
      const content = readFileSync(file, 'utf8');
      for (const name of SERVER_ONLY_ENV) {
        const rel = path.relative(STATIC_DIR, file);
        expect(content.includes(name), `${name} named in ${rel}`).toBe(false);
        expect(content.includes(process.env[name]!), `${name} value in ${rel}`).toBe(false);
      }
    }
  });
});
