export interface PricePoint {
  cropCode: string;
  geography: string;
  date: string;
  price: number;
  currency: string;
  seriesId: string;
  source: string;
}

export interface ClimatePoint {
  geography: string;
  period: string;
  outlook: string;
  sourceDate: string;
  source: string;
}

export interface SuitabilityPoint {
  cropCode: string;
  geography: string;
  layerId: string;
  suitabilityClass: string;
  source: string;
}

export interface WeatherPoint {
  geography: string;
  summary: string;
  retrievedAt: string;
  source: string;
}

export interface YieldPoint {
  cropCode: string;
  geography: string;
  yieldMtPerHa: number | null;
}
