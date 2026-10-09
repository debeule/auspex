import bcrypt from 'bcryptjs';

/**
 * Checks a login against `DASHBOARD_USERNAME` and the bcrypt `DASHBOARD_PASSWORD_HASH`. The hash
 * is compared even for an unknown username, so a wrong name and a wrong password take the same time.
 */
export async function credentialsAreValid(username: string, password: string): Promise<boolean> {
  const expectedUser = process.env.DASHBOARD_USERNAME;
  const hash = process.env.DASHBOARD_PASSWORD_HASH;
  if (!expectedUser || !hash) return false;
  const passwordMatches = await bcrypt.compare(password, hash);
  return passwordMatches && username === expectedUser;
}

export function loginIsConfigured(): boolean {
  return Boolean(
    process.env.DASHBOARD_USERNAME && process.env.DASHBOARD_PASSWORD_HASH && process.env.DASHBOARD_SESSION_SECRET,
  );
}
