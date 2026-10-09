// @vitest-environment node
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import bcrypt from 'bcryptjs';
import { describe, expect, it } from 'vitest';

const SCRIPT = path.resolve(__dirname, '../../scripts/hash-password.mjs');

describe('hash-password script', () => {
  it('test_prints_a_single_quoted_env_line_whose_hash_matches_the_password', () => {
    const run = spawnSync(process.execPath, [SCRIPT], { input: 'correct horse\n', encoding: 'utf8' });

    expect(run.status).toBe(0);
    const match = run.stdout.trim().match(/^DASHBOARD_PASSWORD_HASH='(\$2[aby]\$\d\d\$[./A-Za-z0-9]{53})'$/);
    expect(match).not.toBeNull();
    expect(bcrypt.compareSync('correct horse', match![1])).toBe(true);
    expect(run.stdout).not.toContain('correct horse');
  });

  it('test_empty_password_is_refused', () => {
    const run = spawnSync(process.execPath, [SCRIPT], { input: '\n', encoding: 'utf8' });

    expect(run.status).toBe(1);
    expect(run.stdout).toBe('');
  });
});
