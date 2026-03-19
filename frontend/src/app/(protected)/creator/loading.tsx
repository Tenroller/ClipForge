export default function CreatorLoading() {
  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl animate-in fade-in duration-300">
      <div className="space-y-2 mb-8">
        <div className="h-8 w-44 bg-muted animate-pulse rounded-md" />
        <div className="h-5 w-80 bg-muted animate-pulse rounded-md" />
      </div>
      {/* Form skeleton */}
      <div className="space-y-6">
        <div className="h-12 bg-muted animate-pulse rounded-xl" />
        <div className="h-32 bg-muted animate-pulse rounded-xl" />
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="h-12 bg-muted animate-pulse rounded-xl" />
          <div className="h-12 bg-muted animate-pulse rounded-xl" />
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="h-12 bg-muted animate-pulse rounded-xl" />
          <div className="h-12 bg-muted animate-pulse rounded-xl" />
          <div className="h-12 bg-muted animate-pulse rounded-xl" />
        </div>
        <div className="h-12 bg-muted animate-pulse rounded-xl" />
      </div>
    </div>
  );
}
