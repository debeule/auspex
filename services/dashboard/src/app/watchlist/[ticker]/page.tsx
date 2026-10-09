import CompanyDetail from '@/components/watchlist/CompanyDetail';

export default async function Page({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params;
  return (
    <main className="mx-auto max-w-5xl p-6">
      <CompanyDetail ticker={ticker} />
    </main>
  );
}
