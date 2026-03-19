export default function PodcastClipsLoading() {
  return (
    <div className="container mx-auto px-4 py-8 max-w-7xl animate-in fade-in duration-300">
      <div className="space-y-2 mb-8">
        <div className="h-8 w-48 bg-muted animate-pulse rounded-md" />
        <div className="h-5 w-72 bg-muted animate-pulse rounded-md" />
      </div>
      {/* Tabs skeleton */}
      <div className="flex gap-2 mb-6">
        <div className="h-10 w-28 bg-muted animate-pulse rounded-md" />
        <div className="h-10 w-28 bg-muted animate-pulse rounded-md" />
      </div>
      {/* Source video grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
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
