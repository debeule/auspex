import CompanyDetail from '@/components/watchlist/CompanyDetail';

export default async function Page({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params;
  return (
    <main className="p-8">
      <CompanyDetail ticker={ticker} />
    </main>
  );
}
