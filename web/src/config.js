// Single switch between mock JSON and Member 1's backend.
// Build-time: VITE_USE_MOCK=false VITE_API_BASE_URL=https://<backend> npm run build
// Dev-time:   create web/.env.local with VITE_USE_MOCK=false to try the live API.

export const USE_MOCK =
  (import.meta.env.VITE_USE_MOCK ?? "true").toLowerCase() !== "false";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export const API_PATH = "/api/grci";

// Demo risk bands are display-only. The engine owns classification;
// the UI never recomputes bands. Shown so judges know high/low meaning.
export const DEMO_BANDS_NOTE =
  "Demo bands: low ≤ 1.0, watch 1.0–1.5, high > 1.5 (temporary, not production thresholds).";

export const LUZON_REGIONS = [
  { id: "NCR", label: "NCR — National Capital Region" },
  { id: "CAR", label: "CAR — Cordillera Administrative Region" },
  { id: "I", label: "Region I — Ilocos Region" },
  { id: "II", label: "Region II — Cagayan Valley" },
  { id: "III", label: "Region III — Central Luzon" },
  { id: "IV-A", label: "Region IV-A — CALABARZON" },
  { id: "MIMAROPA", label: "MIMAROPA" },
  { id: "V", label: "Region V — Bicol Region" },
];

export const CROPS = [
  { id: "tomato", label: "Tomato" },
  { id: "eggplant", label: "Eggplant" },
];
