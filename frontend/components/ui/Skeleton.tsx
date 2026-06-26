export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-white/[0.05] ${className}`} />;
}

export function RowSkeleton() {
  return (
    <div className="flex items-center gap-4 py-4 px-6 border-b border-white/[0.05]">
      <Skeleton className="w-11 h-11 rounded-full flex-shrink-0" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-3.5 w-36" />
        <Skeleton className="h-2.5 w-20" />
      </div>
      <Skeleton className="hidden sm:block h-3 w-12" />
      <Skeleton className="hidden md:block h-3 w-32" />
      <Skeleton className="h-3 w-24 ml-auto" />
    </div>
  );
}
