'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function NavBar() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-6 p-4 border-b">
      <Link
        href="/"
        style={{ textDecoration: pathname === '/' ? 'underline' : 'none' }}
      >
        Signals
      </Link>
      <Link
        href="/watchlist"
        style={{ textDecoration: pathname?.startsWith('/watchlist') ? 'underline' : 'none' }}
      >
        Watchlist
      </Link>
    </nav>
  );
}
