// The UI never computes GRCI math. It sends farmer inputs to the local
// Python service and renders the engine result returned inside the envelope.
import { API_PATH, OPTIONS_PATH, USE_MOCK, FIXED_DEMO_OPTIONS } from "../config.js";
import { pickMock } from "../mocks/grciMocks.js";
import { toBackendPayload } from "./grciPayload.js";

async function readJson(response, label) {
  try {
    return await response.json();
  } catch {
    throw new Error(`${label} returned non-JSON response (${response.status}).`);
  }
}

export async function fetchOptions() {
  if (USE_MOCK) return FIXED_DEMO_OPTIONS;

  const response = await fetch(OPTIONS_PATH, { headers: { Accept: "application/json" } });
  const payload = await readJson(response, "Backend options");
  if (!response.ok || payload?.error) {
    throw new Error(payload?.error?.message ?? `Backend returned ${response.status}.`);
  }
  if (
    !Array.isArray(payload?.crops) ||
    !Array.isArray(payload?.regions) ||
    !Array.isArray(payload?.reference_types)
  ) {
    throw new Error("Backend options response is incomplete.");
  }
  return payload;
}

export async function fetchGrci(planInput) {
  if (USE_MOCK) {
    if (!planInput.scenario) {
      throw new Error(
        "Mock fallback only supports the fixed Tomato and Eggplant demo buttons."
      );
    }
    await new Promise((resolve) => setTimeout(resolve, 150));
    return pickMock(planInput);
  }

  const response = await fetch(API_PATH, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(toBackendPayload(planInput)),
  });

  const envelope = await readJson(response, "Backend");
  if (!response.ok || envelope?.error) {
    const message =
      envelope?.error?.message ?? `Backend returned ${response.status}.`;
    throw new Error(message);
  }
  if (!envelope?.result) {
    throw new Error("Backend response has no result.");
  }
  return envelope.result;
}

export { toBackendPayload };
