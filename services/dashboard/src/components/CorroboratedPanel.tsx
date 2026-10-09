import { CorroboratedSignal } from '@/lib/types';
import { formatConfidence, formatUtc } from '@/lib/ticker';
import Table from './ui/Table';

export default function CorroboratedPanel({ signals }: { signals: CorroboratedSignal[] }) {
  return (
    <Table caption="Corroborated signals" headers={['Entity', 'Sources', 'Confidence', 'Corroborated']}>
      {signals.map((s) => (
        <tr key={s.entity_key}>
          <td className="px-2 py-1.5">{s.entity_key}</td>
          <td className="px-2 py-1.5">
            <span className="flex flex-wrap gap-1">
              {s.distinct_source_types.map((st) => (
                <span key={st} className="rounded bg-gray-100 px-1.5 py-0.5 text-xs">
                  {st}
                </span>
              ))}
            </span>
          </td>
          <td className="px-2 py-1.5">{formatConfidence(s.confidence)}</td>
          <td className="px-2 py-1.5 whitespace-nowrap">{formatUtc(s.corroborated_at)}</td>
        </tr>
      ))}
    </Table>
  );
}
