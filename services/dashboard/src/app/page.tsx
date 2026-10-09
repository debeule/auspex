import SignalsDashboard from '@/components/SignalsDashboard';
import PageShell from '@/components/ui/PageShell';

export default function Home() {
  return (
    <PageShell title="Signals">
      <SignalsDashboard />
    </PageShell>
  );
}
