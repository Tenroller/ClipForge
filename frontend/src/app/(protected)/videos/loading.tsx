export default function VideosLoading() {
  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl animate-in fade-in duration-300">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div className="space-y-2">
          <div className="h-8 w-36 bg-muted animate-pulse rounded-md" />
          <div className="h-5 w-56 bg-muted animate-pulse rounded-md" />
        </div>
        <div className="flex gap-2">
          <div className="h-10 w-10 bg-muted animate-pulse rounded-md" />
          <div className="h-10 w-10 bg-muted animate-pulse rounded-md" />
          <div className="h-10 w-28 bg-muted animate-pulse rounded-md" />
        </div>
      </div>
      {/* Stats row */}
      <div className="grid gap-3 sm:grid-cols-4 mb-6">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-20 bg-muted animate-pulse rounded-xl" />
        ))}
      </div>
      {/* Video grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="space-y-2">
            <div className="aspect-video bg-muted animate-pulse rounded-xl" />
            <div className="h-4 w-3/4 bg-muted animate-pulse rounded" />
            <div className="h-3 w-1/2 bg-muted animate-pulse rounded" />
          </div>
        ))}
      </div>
    </div>
  );
}
