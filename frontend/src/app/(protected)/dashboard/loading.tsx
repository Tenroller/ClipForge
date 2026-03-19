export default function DashboardLoading() {
  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl animate-in fade-in duration-300">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div className="space-y-2">
          <div className="h-8 w-40 bg-muted animate-pulse rounded-md" />
          <div className="h-5 w-64 bg-muted animate-pulse rounded-md" />
        </div>
        <div className="h-10 w-28 bg-muted animate-pulse rounded-md" />
      </div>
      {/* Summary cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-28 bg-muted animate-pulse rounded-xl" />
        ))}
      </div>
      {/* Charts row */}
      <div className="grid gap-6 lg:grid-cols-3 mb-8">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-56 bg-muted animate-pulse rounded-xl" />
        ))}
      </div>
      {/* Recent activity */}
      <div className="h-72 bg-muted animate-pulse rounded-xl" />
    </div>
  );
}
