import { CorroboratedSignal } from '@/lib/types';
import { formatConfidence, formatDate } from '@/lib/ticker';

export default function CorroboratedPanel({ signals }: { signals: CorroboratedSignal[] }) {
  return (
    <div>
      {signals.map((s) => (
        <div key={s.entity_key}>
          <span>{s.entity_key}</span>
          <span>{s.distinct_source_types.map((st) => <span key={st}>{st}</span>)}</span>
          <span>{formatConfidence(s.confidence)}</span>
          <span>{formatDate(s.corroborated_at)}</span>
        </div>
      ))}
    </div>
  );
}
