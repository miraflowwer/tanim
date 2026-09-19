const QUALITY_COPY = {
  synthetic: "SYNTHETIC",
  historical_proxy: "HISTORICAL PROXY",
  national_context: "NATIONAL CONTEXT",
  production_baseline: "HISTORICAL BASELINE",
  direct: "COMMITTED LOCAL",
};

export default function EvidenceBadge({ quality, scope }) {
  const label = QUALITY_COPY[quality] ?? (quality || "UNKNOWN").toUpperCase();
  const tone = `tanim-badge-${quality ?? "unknown"}`;
  return (
    <span className={`tanim-badge ${tone}`} title={`Scope: ${scope ?? "unknown"}`}>
      {label}
    </span>
  );
}
