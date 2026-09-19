import EvidenceBadge from "./EvidenceBadge.jsx";

function fmt(value, digits = 4) {
  if (value === null || value === undefined) return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return String(Number(n.toFixed(digits)));
}

function fmtRange(range, unit) {
  if (!range) return "—";
  const [low, high] = range;
  if (Number(low) === Number(high)) return `${fmt(low)} ${unit}`;
  return `${fmt(low)} to ${fmt(high)} ${unit}`;
}

const EVIDENCE_STATUS_COPY = {
  fixed_synthetic: "Fixed synthetic demo fixture — not observed demand.",
  user_provided_unverified:
    "User-provided evidence — not independently reviewed or verified.",
  reviewed_verified: "Reviewed and verified by a trusted source integration.",
};

const OK_STATE_LABELS = {
  risk: "GRCI risk state",
  risk_proxy: "Proxy risk state",
  demo: "Demo risk state",
};

function stateBlock(result) {
  const tone =
    result.status === "ok"
      ? result.risk_state ?? result.comparison_state ?? "unclassified"
      : result.status;
  const cls = `tanim-state-${tone}`;
  if (result.status === "ok") {
    const label = result.risk_state ?? result.comparison_state ?? "—";
    const stateLabel =
      OK_STATE_LABELS[result.reference_mode] ?? "Comparison state";
    return (
      <div className={cls}>
        {stateLabel}: {label}
        {result.borderline ? " (borderline — range crosses bands)" : ""}
      </div>
    );
  }
  if (result.status === "baseline") {
    return (
      <div className={cls}>
        Baseline comparison (not a demand risk):{" "}
        {result.comparison_state ?? "—"}
        {result.borderline ? " (borderline)" : ""}
      </div>
    );
  }
  if (result.status === "context_only") {
    return <div className={cls}>Context only — no local comparison</div>;
  }
  return <div className={cls}>Status: {result.status}</div>;
}

export default function ResultCard({ result, plan }) {
  if (!result) return null;
  const areaRange = result.planned_area_range;
  const isRange =
    areaRange && Number(areaRange[0]) !== Number(areaRange[1]);
  const canSayDemand =
    result.market_demand_wording_allowed === true &&
    result.evidence_status === "reviewed_verified";
  const evidenceStatus =
    EVIDENCE_STATUS_COPY[result.evidence_status] ??
    "Evidence status is not available.";

  return (
    <section className="tanim-card" aria-label="Plan result" aria-live="polite">
      <h2>2. Your result</h2>
      {stateBlock(result)}
      <div className="tanim-result-grid" style={{ marginTop: "1rem" }}>
        <div className="tanim-result-row">
          <span className="tanim-result-label">Planned area</span>
          <span className="tanim-result-value">
            {fmtRange(areaRange, "ha")}
          </span>
        </div>
        {isRange && (
          <div className="tanim-result-row">
            <span className="tanim-result-label">Estimated area range</span>
            <span className="tanim-result-value">
              Estimated range: {fmt(areaRange[0])} ha to {fmt(areaRange[1])}{" "}
              ha (from your ± margin — not a statistical interval)
            </span>
          </div>
        )}
        <div className="tanim-result-row">
          <span className="tanim-result-label">Reference yield</span>
          <span className="tanim-result-value">
            {result.reference_yield === null ||
            result.reference_yield === undefined
              ? "Missing — expected production cannot be calculated."
              : `${fmt(result.reference_yield)} MT/ha (${result.yield_source ?? "unknown source"})`}
          </span>
        </div>
        <div className="tanim-result-row">
          <span className="tanim-result-label">Expected production</span>
          <span className="tanim-result-value">
            {fmtRange(result.expected_production_range, "MT")}
          </span>
        </div>
        <div className="tanim-result-row">
          <span className="tanim-result-label">Comparison reference</span>
          <span className="tanim-result-value">
            {result.reference_amount ?? "—"} {result.reference_unit ?? ""} ·{" "}
            {result.reference_geography ?? "—"} ·{" "}
            {result.reference_period ?? "—"}
          </span>
          <span className="tanim-hint">
            {canSayDemand
              ? "This reference may be called market demand."
              : "This reference must NOT be called market demand."}
          </span>
        </div>
        <div className="tanim-result-row">
          <span className="tanim-result-label">Reference type</span>
          <span className="tanim-result-value">
            <EvidenceBadge
              quality={result.reference_quality}
              scope={result.reference_scope}
              evidenceStatus={result.evidence_status}
            />
            <br />
            {result.reference_label ?? result.reference_type ?? "—"}
            <br />
            <span className="tanim-hint">Code: {result.reference_type}</span>
          </span>
        </div>
        <div className="tanim-result-row">
          <span className="tanim-result-label">Evidence status</span>
          <span className="tanim-result-value">
            {evidenceStatus}
          </span>
        </div>
        <div className="tanim-result-row">
          <span className="tanim-result-label">Evidence note</span>
          <div className="tanim-evidence">
            {result.reference_evidence_note ?? "—"}
          </div>
        </div>
        <div className="tanim-result-row">
          <span className="tanim-result-label">
            GRCI / comparison state
          </span>
          <span className="tanim-result-value">
            Supply load:{" "}
            {result.supply_load_range
              ? fmtRange(result.supply_load_range, "ratio")
              : "not computed for this reference"}
            <br />
            Comparison: {result.comparison_state ?? "—"}
            {result.comparison_band_range
              ? ` (${result.comparison_band_range.join(" → ")})`
              : ""}
            <br />
            Risk: {result.risk_state ?? "—"}
            {result.risk_band_range
              ? ` (${result.risk_band_range.join(" → ")})`
              : ""}
          </span>
        </div>
        <div className="tanim-result-row">
          <span className="tanim-result-label">Uncertainty</span>
          <span className="tanim-result-value">
            {result.uncertainty_note ?? "—"}
            <br />
            <span className="tanim-hint">
              State: {result.uncertainty_state ?? "—"}
            </span>
          </span>
        </div>
        <div className="tanim-result-row">
          <span className="tanim-result-label">Short explanation</span>
          <span className="tanim-result-value">{result.explanation}</span>
        </div>
        {plan && (
          <div className="tanim-result-row">
            <span className="tanim-result-label">Your plan</span>
            <span className="tanim-hint">
              {Array.isArray(plan.plans) ? `${plan.plans.length} farmer plans · ` : ""}
              {plan.crop} · {plan.location} · planted {plan.plantingDate} ·
              harvest {plan.harvestPeriod}
            </span>
          </div>
        )}
        <details className="tanim-provenance">
          <summary>Provenance / sources (for judges)</summary>
          <div>
            Sources:{" "}
            {(result.source_labels ?? []).join(", ") || "—"}
            <br />
            <code style={{ wordBreak: "break-all" }}>
              {JSON.stringify(result.provenance)}
            </code>
          </div>
        </details>
      </div>
    </section>
  );
}
