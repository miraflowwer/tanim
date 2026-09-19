// Fixed, committed synthetic fixtures only. No unverified buyer-demand mock is
// exposed through the UI.
export default function DemoPresets({ onPreset, disabled }) {
  return (
    <div className="tanim-card" aria-label="Demo shortcuts">
      <h2>Fixed demo — Tomato &amp; Eggplant</h2>
      <p className="tanim-hint" style={{ marginTop: 0 }}>
        DEMO-2026 is synthetic. Tomato uses four 10 ha plans. Eggplant uses
        two 4 ha plans. These values are never presented as observed market
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
    </div>
  );
}
