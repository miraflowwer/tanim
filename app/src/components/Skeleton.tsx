export function Skeleton({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" aria-label={label}>
      <div className="skeleton" />
      <span className="hint">{label}</span>
    </div>
  );
}
