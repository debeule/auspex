import { DirectSignal } from '@/lib/types';
import { formatConfidence, formatDate } from '@/lib/ticker';

export default function DirectSignalsTable({ signals }: { signals: DirectSignal[] }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Title</th>
          <th>Source</th>
          <th>Confidence</th>
          <th>Published</th>
        </tr>
      </thead>
      <tbody>
        {signals.map((s) => (
          <tr key={s.event_id}>
            <td>{s.title}</td>
            <td>{s.source_type}</td>
            <td>{formatConfidence(s.confidence_score)}</td>
            <td>{formatDate(s.published_at)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
