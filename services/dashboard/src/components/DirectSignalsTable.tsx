import { DirectSignal } from '@/lib/types';
import { formatConfidence, formatUtc } from '@/lib/ticker';
import Table from './ui/Table';

export default function DirectSignalsTable({ signals }: { signals: DirectSignal[] }) {
  return (
    <Table caption="Direct signals" headers={['Title', 'Source', 'Confidence', 'Published']}>
      {signals.map((s) => (
        <tr key={s.event_id}>
          <td className="px-2 py-1.5">{s.title}</td>
          <td className="px-2 py-1.5">{s.source_type}</td>
          <td className="px-2 py-1.5">{formatConfidence(s.confidence_score)}</td>
          <td className="px-2 py-1.5 whitespace-nowrap">{formatUtc(s.published_at)}</td>
        </tr>
      ))}
    </Table>
  );
}
