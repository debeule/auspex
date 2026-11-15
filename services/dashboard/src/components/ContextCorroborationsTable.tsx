import { ContextCorroboration } from '@/lib/types';
import { formatUtc } from '@/lib/ticker';
import Table from './ui/Table';

const REASONS: Record<ContextCorroboration['reason'], string> = {
  broad_entity: 'Broad entity',
  no_independent_pair_for_ticker: 'No independent pair for this ticker',
};

/** Context corroborations (DSH-019): shown for reference, never scored or traded. */
export default function ContextCorroborationsTable({ items }: { items: ContextCorroboration[] }) {
  return (
    <Table caption="Context corroborations" headers={['Entity', 'Reason', 'Sources', 'Opened']}>
      {items.map((c) => (
        <tr key={c.entity_key + c.episode_opened_at}>
          <td className="px-2 py-1.5">{c.entity_key}</td>
          <td className="px-2 py-1.5">{REASONS[c.reason] ?? c.reason}</td>
          <td className="px-2 py-1.5">{c.distinct_source_types.join(', ')}</td>
          <td className="px-2 py-1.5 whitespace-nowrap">{formatUtc(c.episode_opened_at)}</td>
        </tr>
      ))}
    </Table>
  );
}
