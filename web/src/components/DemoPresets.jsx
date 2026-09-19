// One-click inputs for the fixed Tomato/Eggplant demo + wording-guard demos.
// These only fill the form / pick a mock scenario — no math happens here.
export default function DemoPresets({ onPreset, disabled }) {
  return (
    <div className="tanim-card" aria-label="Demo shortcuts">
      <h2>Fixed demo — Tomato &amp; Eggplant</h2>
      <p className="tanim-hint" style={{ marginTop: 0 }}>
        Reproducible DEMO-2026 values. Always labelled synthetic, never market
        demand.
      </p>
      <div className="tanim-demo-bar">
        <button
          className="tanim-btn tanim-btn-secondary"
          type="button"
          disabled={disabled}
          onClick={() => onPreset("tomato-demo")}
        >
          Tomato demo (high)
        </button>
        <button
          className="tanim-btn tanim-btn-secondary"
          type="button"
          disabled={disabled}
          onClick={() => onPreset("eggplant-demo")}
        >
          Eggplant demo (low)
        </button>
      </div>
      <div className="tanim-demo-bar">
        <button
          className="tanim-btn tanim-btn-secondary"
          type="button"
          disabled={disabled}
          onClick={() => onPreset("tomato-baseline")}
        >
          Baseline wording
        </button>
        <button
          className="tanim-btn tanim-btn-secondary"
          type="button"
          disabled={disabled}
          onClick={() => onPreset("tomato-context")}
        >
          National context
        </button>
      </div>
    </div>
  );
}
