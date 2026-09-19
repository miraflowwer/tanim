import { ACCESS_TOKEN_KEY, ServerError, isServerError } from "../../lib/api";
import type { ClimatePoint, PricePoint, SuitabilityPoint, WeatherPoint, YieldPoint } from "./context.types";

function authed(): HeadersInit {
  const token = window.localStorage.getItem(ACCESS_TOKEN_KEY);
  return token
    ? { "content-type": "application/json", authorization: `Bearer ${token}` }
    : { "content-type": "application/json" };
}

async function getJson(path: string): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(path, { headers: authed() });
  } catch {
    throw new ServerError("SERVICE_UNAVAILABLE", 0);
  }
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ServerError("SERVICE_UNAVAILABLE", response.status);
  return payload;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function text(value: unknown, fallback: string): string {
  return typeof value === "string" && value.length > 0 ? value : fallback;
}

function decimalOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

// Prices are context only, never a demand reference.
export async function fetchPriceSeries(cropCode?: string): Promise<PricePoint[]> {
  const query = cropCode ? `?crop_code=${encodeURIComponent(cropCode)}` : "";
  const payload = await getJson(`/api/v1/prices${query}`);
  if (!isRecord(payload) || !Array.isArray(payload.prices)) {
    throw new ServerError("SERVICE_UNAVAILABLE", 200);
  }
  return payload.prices.flatMap((entry): PricePoint[] => {
    if (!isRecord(entry)) return [];
    return [{
      cropCode: text(entry.crop_code, ""),
      geography: text(entry.geography, ""),
      date: text(entry.observed_on, ""),
      price: decimalOrNull(entry.price) ?? 0,
      currency: text(entry.currency, "PHP"),
      seriesId: text(entry.series_id, ""),
      source: text(entry.source, ""),
    }];
  });
}

export async function fetchClimate(geography?: string): Promise<ClimatePoint[]> {
  const query = geography ? `?geography=${encodeURIComponent(geography)}` : "";
  const payload = await getJson(`/api/v1/context/climate${query}`);
  if (!isRecord(payload) || !Array.isArray(payload.climate)) {
    throw new ServerError("SERVICE_UNAVAILABLE", 200);
  }
  return payload.climate.flatMap((entry): ClimatePoint[] => {
    if (!isRecord(entry)) return [];
    return [{
      geography: text(entry.geography, ""),
      period: text(entry.period, ""),
      outlook: text(entry.outlook, ""),
      sourceDate: text(entry.source_date, ""),
      source: text(entry.source, ""),
    }];
  });
}

export async function fetchSuitability(cropCode?: string): Promise<SuitabilityPoint[]> {
  const query = cropCode ? `?crop_code=${encodeURIComponent(cropCode)}` : "";
  const payload = await getJson(`/api/v1/context/suitability${query}`);
  if (!isRecord(payload) || !Array.isArray(payload.suitability)) {
    throw new ServerError("SERVICE_UNAVAILABLE", 200);
  }
  return payload.suitability.flatMap((entry): SuitabilityPoint[] => {
    if (!isRecord(entry)) return [];
    return [{
      cropCode: text(entry.crop_code, ""),
      geography: text(entry.geography, ""),
      layerId: text(entry.layer_id, ""),
      suitabilityClass: text(entry.suitability_class, ""),
      source: text(entry.source, ""),
    }];
  });
}

export async function fetchWeatherSnapshot(geography: string): Promise<WeatherPoint | null> {
  const payload = await getJson(`/api/v1/context/weather?geography=${encodeURIComponent(geography)}`);
  if (!isRecord(payload)) return null;
  if (!payload.summary && !payload.geography) return null;
  return {
    geography: text(payload.geography, geography),
    summary: text(payload.summary, "No summary returned."),
    retrievedAt: text(payload.retrieved_at, ""),
    source: text(payload.source, ""),
  };
}

export async function fetchCropYield(cropCode: string, geography: string): Promise<YieldPoint> {
  const payload = await getJson(
    `/api/v1/crops/${encodeURIComponent(cropCode)}/yield?geography=${encodeURIComponent(geography)}`,
  );
  if (!isRecord(payload)) throw new ServerError("SERVICE_UNAVAILABLE", 200);
  const candidates = [payload.yield_mt_per_ha, payload.yield, payload.value];
  let found: number | null = null;
  for (const candidate of candidates) {
    const parsed = decimalOrNull(candidate);
    if (parsed !== null) {
      found = parsed;
      break;
    }
  }
  return {
    cropCode: text(payload.crop_code, cropCode),
    geography: text(payload.geography, geography),
    yieldMtPerHa: found,
  };
}

export { isServerError };
