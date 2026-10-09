/** A data table; `caption` names it for assistive technology and is visually hidden. */
export default function Table({
  caption,
  headers,
  children,
}: {
  caption: string;
  headers: string[];
  children: React.ReactNode;
}) {
  return (
    <table className="w-full border-collapse text-left text-sm">
      <caption className="sr-only">{caption}</caption>
      <thead className="border-b border-gray-200 text-gray-600">
        <tr>
          {headers.map((h) => (
            <th key={h} scope="col" className="px-2 py-1.5 font-medium">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-gray-100">{children}</tbody>
    </table>
  );
}
