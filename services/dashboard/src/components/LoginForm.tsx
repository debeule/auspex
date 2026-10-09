'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, errorMessage } from '@/lib/api';
import Button from './ui/Button';
import FormField from './ui/FormField';
import { ErrorMessage } from './ui/Status';

/** Only a path on this origin is followed after sign-in; anything else lands on the home page. */
function safeNext(next: string): string {
  return next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/\\') ? next : '/';
}

export default function LoginForm({ next }: { next: string }) {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.auth.login(username, password);
      router.replace(safeNext(next));
      router.refresh();
    } catch (err) {
      setError(errorMessage(err));
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <FormField
        id="login-username"
        label="Username"
        autoComplete="username"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        required
      />
      <FormField
        id="login-password"
        label="Password"
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />
      {error && <ErrorMessage>{error}</ErrorMessage>}
      <Button type="submit" disabled={submitting}>
        Sign in
      </Button>
    </form>
  );
}
