// Prints a .env line holding the bcrypt hash of a password read from stdin, without echoing it.
// The value is single-quoted because bcrypt hashes contain `$`, which docker compose would
// otherwise treat as a variable reference.
import { createInterface } from 'node:readline';
import { Writable } from 'node:stream';
import bcrypt from 'bcryptjs';

const COST = 12; // bcrypt work factor: 2^12 rounds

const silent = new Writable({ write: (_chunk, _encoding, done) => done() });
const rl = createInterface({ input: process.stdin, output: silent, terminal: Boolean(process.stdin.isTTY) });
if (process.stdin.isTTY) process.stderr.write('Password: ');
rl.once('line', (password) => {
  rl.close();
  if (!password) {
    process.stderr.write('\nNo password given.\n');
    process.exit(1);
  }
  process.stdout.write(`DASHBOARD_PASSWORD_HASH='${bcrypt.hashSync(password, COST)}'\n`);
});
