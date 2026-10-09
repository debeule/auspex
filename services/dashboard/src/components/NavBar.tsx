'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import Button from './ui/Button';

const LINKS = [
  { href: '/', label: 'Signals', active: (p: string) => p === '/' },
  { href: '/watchlist', label: 'Watchlist', active: (p: string) => p.startsWith('/watchlist') },
];

export default function NavBar() {
  const pathname = usePathname() ?? '/';
  const router = useRouter();

  if (pathname === '/login') return null;

  async function signOut() {
    try {
      await api.auth.logout();
    } finally {
      router.replace('/login');
    }
  }

  return (
    <nav className="flex items-center gap-6 border-b border-gray-200 bg-white px-6 py-3">
      <span className="font-semibold">Auspex</span>
      {LINKS.map(({ href, label, active }) => (
        <Link
          key={href}
          href={href}
          aria-current={active(pathname) ? 'page' : undefined}
          className="text-sm text-gray-700 hover:text-gray-900 aria-[current=page]:font-semibold aria-[current=page]:underline"
        >
          {label}
        </Link>
      ))}
      <Button variant="secondary" className="ml-auto" onClick={signOut}>
        Sign out
      </Button>
    </nav>
  );
}
