export function CardSkeleton() {
  return <div className="glass-card p-4 h-24 animate-pulse bg-white/5" />;
}

export function BlockSkeleton({ height = "h-64" }) {
  return <div className={`glass-card ${height} animate-pulse bg-white/5`} />;
}

export function SkeletonGrid({ count = 4 }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <CardSkeleton key={i} />
      ))}
    </div>
  );
}
