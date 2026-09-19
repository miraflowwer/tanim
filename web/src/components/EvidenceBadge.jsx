const QUALITY_COPY = {
  synthetic: "SYNTHETIC",
  historical_proxy: "HISTORICAL PROXY",
  national_context: "NATIONAL CONTEXT",
  production_baseline: "HISTORICAL BASELINE",
  direct: "REVIEWED LOCAL",
};

export default function EvidenceBadge({ quality, scope, evidenceStatus }) {
  const label =
    quality === "direct" && evidenceStatus !== "reviewed_verified"
      ? "UNVERIFIED LOCAL"
      : QUALITY_COPY[quality] ?? (quality || "UNKNOWN").toUpperCase();
  const tone = `tanim-badge-${quality ?? "unknown"}`;
  return (
    <span className={`tanim-badge ${tone}`} title={`Scope: ${scope ?? "unknown"}`}>
      {label}
    </span>
  );
}
