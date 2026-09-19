import SignalsDashboard from '@/components/SignalsDashboard';

export default function Home() {
  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold mb-6">Auspex Signal Dashboard</h1>
      <SignalsDashboard />
    </main>
  );
}
