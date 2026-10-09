export function Loading({ children }: { children: React.ReactNode }) {
  return (
    <p role="status" className="text-sm text-gray-500">
      {children}
    </p>
  );
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-gray-500">{children}</p>;
}

export function ErrorMessage({ children }: { children: React.ReactNode }) {
  return (
    <p role="alert" className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
      {children}
    </p>
  );
}
