// Step 7 runs against the local Python service by default.
// Set VITE_USE_MOCK=true only for the fixed offline UI fallback.

export const USE_MOCK =
  (import.meta.env.VITE_USE_MOCK ?? "false").toLowerCase() === "true";

export const API_PATH = "/api/grci";
export const OPTIONS_PATH = "/api/options";

export const DEMO_BANDS_NOTE =
  "Demo bands: low ≤ 1.0, watch 1.0–1.5, high > 1.5 (temporary, not production thresholds).";

export const FIXED_DEMO_OPTIONS = {
  crops: [
    { id: "tomato", label: "Tomato", regions: ["IV-A"], demo_regions: ["IV-A"] },
    { id: "eggplant", label: "Eggplant", regions: ["IV-A"], demo_regions: ["IV-A"] },
  ],
  regions: [{ id: "IV-A", label: "Region IV-A — CALABARZON" }],
  reference_types: [],
};
