import { useEffect, useState } from "react";
import PlanForm from "./components/PlanForm.jsx";
import DemoPresets from "./components/DemoPresets.jsx";
import ResultCard from "./components/ResultCard.jsx";
import { fetchGrci, fetchOptions } from "./api/grciClient.js";
import { DEMO_BANDS_NOTE, FIXED_DEMO_OPTIONS, USE_MOCK } from "./config.js";

function planForScenario(scenario) {
  const eggplant = scenario === "eggplant-demo";
  const crop = eggplant ? "eggplant" : "tomato";
  const count = eggplant ? 2 : 4;
  const farmSizeHa = eggplant ? 4 : 10;
  const plans = Array.from({ length: count }, () => ({
    crop,
    regionId: "IV-A",
    location: "Tanauan, Batangas",
    farmSizeHa,
    farmSizeMarginHa: 0,
    plantingDate: "2026-09-01",
    harvestPeriod: "2026-12",
  }));

  return {
    crop,
    regionId: "IV-A",
    location: "Tanauan, Batangas",
    farmSizeHa,
    farmSizeMarginHa: 0,
    plantingDate: "2026-09-01",
    harvestPeriod: "2026-12",
    useDemoReference: true,
    scenario,
    plans,
  };
}

export default function App() {
  const [result, setResult] = useState(null);
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [presetPlan, setPresetPlan] = useState(null);
  const [options, setOptions] = useState(
    USE_MOCK ? FIXED_DEMO_OPTIONS : null
  );
  const [optionsError, setOptionsError] = useState("");

  useEffect(() => {
    let active = true;
    fetchOptions()
      .then((next) => {
        if (!active) return;
        setOptions(next);
        setOptionsError("");
      })
      .catch((err) => {
        if (!active) return;
        setOptionsError(
          err instanceof Error
            ? err.message
            : "Could not load planning options from the backend."
        );
      });
    return () => {
      active = false;
    };
  }, []);

  async function run(planInput) {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await fetchGrci(planInput);
      setPlan(planInput);
      setResult(res);
    } catch (err) {
      setPlan(planInput);
      setError(err instanceof Error ? err.message : "Could not load result.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="tanim-app">
      <header className="tanim-header">
        <h1>TANIM — Planting Plan</h1>
        <p>
          Enter a planting plan and see expected production plus the exact
          evidence used for comparison.
        </p>
        <p className="tanim-hint">
          {USE_MOCK
            ? "Fixed mock fallback is ON. Only the two locked demo fixtures are available."
            : "Using the local TANIM backend. No external PSA call is made during the demo."}
        </p>
        <p className="tanim-hint">{DEMO_BANDS_NOTE}</p>
      </header>

      <DemoPresets
        disabled={loading}
        onPreset={(scenario) => {
          const nextPlan = planForScenario(scenario);
          setPresetPlan(nextPlan);
          run(nextPlan);
        }}
      />

      {USE_MOCK ? (
        <section className="tanim-card" aria-label="Fixed fallback mode">
          <h2>Fixed fallback mode</h2>
          <p className="tanim-hint">
            Use the Tomato or Eggplant demo buttons above. Normal farmer plans
            require the local backend so TANIM can validate crop, yield, and
            comparison evidence.
          </p>
        </section>
      ) : optionsError ? (
        <section className="tanim-card" aria-label="Planning options unavailable">
          <h2>Planning form unavailable</h2>
          <div className="tanim-error" role="alert">
            {optionsError}
          </div>
          <p className="tanim-hint">
            The form is disabled because crop and region choices could not be
            verified from the local backend.
          </p>
        </section>
      ) : options ? (
        <PlanForm
          loading={loading}
          onSubmit={run}
          preset={presetPlan}
          options={options}
          optionsError=""
        />
      ) : (
        <section className="tanim-card" aria-live="polite">
          <h2>Loading planning form</h2>
          <p className="tanim-hint">
            Checking committed crop and regional yield coverage.
          </p>
        </section>
      )}

      {error && (
        <div className="tanim-error" role="alert">
          {error}
        </div>
      )}

      <ResultCard result={result} plan={plan} />

      <footer className="tanim-footer">
        Historical yield is a production reference, not market demand. National
        figures are context only. Synthetic demo values are always labelled.
      </footer>
    </div>
  );
}
