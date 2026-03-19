export default function ProtectedLoading() {
  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl animate-in fade-in duration-300">
      {/* Header skeleton */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div className="space-y-2">
          <div className="h-8 w-48 bg-muted animate-pulse rounded-md" />
          <div className="h-5 w-72 bg-muted animate-pulse rounded-md" />
        </div>
      </div>
      {/* Content skeleton */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="h-40 bg-muted animate-pulse rounded-xl"
          />
        ))}
      </div>
    </div>
  );
}
