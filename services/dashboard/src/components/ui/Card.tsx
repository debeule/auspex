export default function Card({ title, children }: { title?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="space-y-3 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      {title && <h2 className="text-lg font-medium">{title}</h2>}
      {children}
    </section>
  );
}
