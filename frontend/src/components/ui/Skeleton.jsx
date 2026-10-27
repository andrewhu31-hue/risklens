export function BlockSkeleton({ height = "h-64" }) {
  return <div className={`panel ${height} animate-pulse bg-rule-soft/60`} aria-busy="true" aria-label="Loading" />;
}

export function SkeletonGrid({ count = 4 }) {
  const rows = Math.ceil(count / 4);
  return <BlockSkeleton height={rows > 1 ? "h-48" : "h-24"} />;
}

export function ErrorNote({ children }) {
  return (
    <div role="alert" className="panel border-loss/30 px-4 py-3 text-sm text-loss">
      {children}
    </div>
  );
}
