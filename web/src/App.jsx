import { useState } from "react";
import PlanForm from "./components/PlanForm.jsx";
import DemoPresets from "./components/DemoPresets.jsx";
import ResultCard from "./components/ResultCard.jsx";
import { fetchGrci } from "./api/grciClient.js";
import { DEMO_BANDS_NOTE, USE_MOCK } from "./config.js";
import { mocksByScenario } from "./mocks/grciMocks.js";

function planForScenario(scenario) {
  if (scenario === "eggplant-demo") {
    return {
      crop: "eggplant",
      regionId: "IV-A",
      location: "Tanauan, Batangas",
      farmSizeHa: 8,
      farmSizeMarginHa: 0,
      plantingDate: "2026-09-01",
      harvestPeriod: "2026-12",
      scenario,
    };
  }
  return {
    crop: "tomato",
    regionId: "IV-A",
    location: "Tanauan, Batangas",
    farmSizeHa: scenario === "tomato-demo" ? 40 : 2,
    farmSizeMarginHa: 0,
    plantingDate: "2026-09-01",
    harvestPeriod: "2026-12",
    scenario,
  };
}

export default function App() {
  const [result, setResult] = useState(null);
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function run(planInput) {
    setLoading(true);
    setError("");
    try {
      const res = await fetchGrci(planInput);
      setPlan(planInput);
      setResult(res);
    } catch (err) {
      setError(
        `Could not load result (${err.message}). Mock mode is ${USE_MOCK ? "ON" : "OFF"}.`
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="tanim-app">
      <header className="tanim-header">
        <h1>TANIM — Planting Plan</h1>
        <p>
          Step 7 farmer demo. Enter your plan, see expected production and a
          clearly labelled comparison. {USE_MOCK ? "Using mock data." : "Using live backend."}
        </p>
        <p className="tanim-hint">{DEMO_BANDS_NOTE}</p>
      </header>

      <DemoPresets
        disabled={loading}
        onPreset={(scenario) => {
          if (mocksByScenario[scenario]) {
            run(planForScenario(scenario));
          }
        }}
      />

      <PlanForm loading={loading} onSubmit={run} />

      {error && (
        <div className="tanim-error" role="alert">
          {error}
        </div>
      )}

      <ResultCard result={result} plan={plan} />

      <footer className="tanim-footer">
        Historical yield is a production reference, not market demand. National
        figures are context only, never local demand. Synthetic demo values are
        always labelled.
      </footer>
    </div>
  );
}
