// Single entry point for GRCI results. The UI never computes GRCI math.
// Mock mode returns precomputed mock JSON. Live mode POSTs the plan input
// to Member 1's backend, which must return the exact compute_grci() shape.
// See web/openapi-note.md.
import { API_BASE_URL, API_PATH, USE_MOCK } from "../config.js";
import { pickMock } from "../mocks/grciMocks.js";

function endpoint() {
  if (!API_BASE_URL) return API_PATH;
  return `${API_BASE_URL.replace(/\/$/, "")}${API_PATH}`;
}

export async function fetchGrci(planInput) {
  if (USE_MOCK) {
    // Keep the async shape so switching to live needs no UI change.
    await new Promise((resolve) => setTimeout(resolve, 350));
    return pickMock(planInput);
  }

  const response = await fetch(endpoint(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(toBackendPayload(planInput)),
  });
  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }
  return response.json();
}

// Maps the farmer form to the backend request shape. Field names match
// scripts/grci.py compute_grci() arguments + plan row keys.
export function toBackendPayload(planInput) {
  return {
    crop: planInput.crop,
    location: planInput.location,
    harvest_period: planInput.harvestPeriod,
    plans: [
      {
        crop_canonical: planInput.crop,
        municipality: planInput.location,
        harvest_period: planInput.harvestPeriod,
        farm_size_ha: planInput.farmSizeHa,
        farm_size_margin_ha: planInput.farmSizeMarginHa,
      },
    ],
    planting_date: planInput.plantingDate ?? null,
    region_id: planInput.regionId ?? null,
  };
}
