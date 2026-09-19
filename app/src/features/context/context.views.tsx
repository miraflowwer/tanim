import { useEffect, useState } from "react";
import { Alert } from "../../components/Alert";
import { DataTable } from "../../components/DataTable";
import { EmptyState } from "../../components/EmptyState";
import { Select } from "../../components/Select";
import { Skeleton } from "../../components/Skeleton";
import { Status } from "../../components/Status";
import { BarChart } from "../../components/charts/BarChart";
import { LineChart } from "../../components/charts/LineChart";
import { MapPanel, type MapSummaryRow } from "../../components/map/MapPanel";
import { fetchAggregates, fetchReferences, isServerError } from "../../lib/api";
import { ORG_ID } from "../../lib/store";
import type { AggregateRow, ReferenceRecord } from "../../types";
import { harvestBuckets } from "../coordination/coordination.logic";
import {
  fetchClimate,
  fetchCropYield,
  fetchPriceSeries,
  fetchSuitability,
  fetchWeatherSnapshot,
} from "./context.api";
import type {
  ClimatePoint,
  PricePoint,
  SuitabilityPoint,
  WeatherPoint,
  YieldPoint,
} from "./context.types";

export function CoordinatorMap() {
  const [rows, setRows] = useState<MapSummaryRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchAggregates(ORG_ID).then((aggregates) => {
      if (!active) return;
      setRows(aggregates.map((row) => ({
        geography: "Organization scope",
        crop: row.cropCode,
        plans: row.plans,
        farmers: row.farmers,
        areaHa: row.plannedAreaHa,
        productionMt: row.estimatedProductionMt,
        state: row.estimatedProductionMt === null ? "Yield unavailable" : "API aggregate",
      })));
      setError(null);
    }).catch((reason: unknown) => {
      if (active) setError(isServerError(reason) ? reason.message : "The map data is unavailable.");
    });
    return () => { active = false; };
  }, []);

  if (error) return <Alert tone="error" title="Map unavailable">{error}</Alert>;
  if (rows === null) return <Skeleton label="Loading map aggregates" />;
  return (
    <section aria-labelledby="coordmap-h">
      <h2 id="coordmap-h">Coordinator map</h2>
      <MapPanel title="Group aggregates by geography" rows={rows} />
    </section>
  );
}

export function HarvestConcentration() {
  const [mode, setMode] = useState<"Hectares" | "Metric tons">("Hectares");
  const [buckets, setBuckets] = useState<{ period: string; areaHa: number; productionMt: number | null }[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchAggregates(ORG_ID).then((rows) => {
      if (!active) return;
      setBuckets(harvestBuckets(rows));
      setError(null);
    }).catch((reason: unknown) => {
      if (active) setError(isServerError(reason) ? reason.message : "Concentration data is unavailable.");
    });
    return () => { active = false; };
  }, []);

  if (error) return <Alert tone="error" title="Chart unavailable">{error}</Alert>;
  if (buckets === null) return <Skeleton label="Loading harvest concentration" />;
  // Hectares and metric tons never share one ambiguous axis.
  const bars = mode === "Hectares"
    ? buckets.map((bucket) => ({ label: bucket.period, value: bucket.areaHa }))
    : buckets.map((bucket) => ({
        label: bucket.period,
        value: bucket.productionMt,
      }));
  return (
    <section aria-labelledby="harv-h">
      <h2 id="harv-h">Harvest concentration</h2>
      <div className="filters" role="search" aria-label="Chart measure">
        <Select name="harv-mode" label="Measure" options={["Hectares", "Metric tons"]} value={mode}
          onChange={(event) => setMode(event.target.value === "Metric tons" ? "Metric tons" : "Hectares")} />
      </div>
      <BarChart
        title={mode === "Hectares" ? "Planned area by harvest period" : "Estimated production by harvest period"}
        unit={mode === "Hectares" ? "ha" : "MT"}
        bars={bars}
        emptyNote="Yield unavailable"
      />
    </section>
  );
}

export function SupplyVsReference({ cropCode }: { cropCode: string }) {
  const [aggregates, setAggregates] = useState<AggregateRow[] | null>(null);
  const [references, setReferences] = useState<ReferenceRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([fetchAggregates(ORG_ID), fetchReferences(ORG_ID)]).then(([rows, refs]) => {
      if (!active) return;
      setAggregates(rows);
      setReferences(refs);
      setError(null);
    }).catch((reason: unknown) => {
      if (active) setError(isServerError(reason) ? reason.message : "Comparison data is unavailable.");
    });
    return () => { active = false; };
  }, []);

  if (error) return <Alert tone="error" title="Comparison unavailable">{error}</Alert>;
  if (aggregates === null) return <Skeleton label="Loading comparison" />;
  const rows = aggregates.filter((row) => row.cropCode === cropCode);
  const production = rows.reduce<number | null>(
    (sum, row) => (sum === null || row.estimatedProductionMt === null ? null : sum + row.estimatedProductionMt),
    0,
  );
  const verified = references.find(
    (reference) => reference.cropCode === cropCode && reference.workflow === "verified",
  );
  const points = [
    { label: "Estimated production", value: production },
    { label: "Reviewed reference", value: verified ? verified.amountMt : null },
  ];
  if (production === null || !verified) {
    return (
      <section aria-labelledby="svr-h">
        <h2 id="svr-h">Supply vs reviewed reference</h2>
        <p role="status">More evidence needed. Missing values are not plotted as zero.</p>
        <LineChart title="Supply vs reviewed reference" unit="MT" points={points} emptyNote="More evidence needed" />
      </section>
    );
  }
  return (
    <section aria-labelledby="svr-h">
      <h2 id="svr-h">Supply vs reviewed reference</h2>
      <LineChart title="Supply vs reviewed reference" unit="MT" points={points} emptyNote="More evidence needed" />
    </section>
  );
}

export function PriceHistory({ cropCode }: { cropCode: string }) {
  const [points, setPoints] = useState<PricePoint[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchPriceSeries(cropCode).then((series) => {
      if (!active) return;
      setPoints(series);
      setError(null);
    }).catch((reason: unknown) => {
      if (active) setError(isServerError(reason) ? reason.message : "Price history is unavailable.");
    });
    return () => { active = false; };
  }, [cropCode]);

  if (error) return <Alert tone="error" title="Price history unavailable">{error}</Alert>;
  if (points === null) return <Skeleton label="Loading price history" />;
  return (
    <LineChart
      title="Price history"
      unit="PHP/kg"
      points={points.map((point) => ({ label: point.date, value: point.price }))}
      emptyNote="No price observations"
      contextNote="Market price context. This is not the reviewed comparison reference used for the coordination result."
    />
  );
}

export function CoordinatorTimeline() {
  const [cropF, setCropF] = useState("All");
  const [buckets, setBuckets] = useState<{ period: string; areaHa: number; productionMt: number | null }[] | null>(null);
  const [aggregates, setAggregates] = useState<AggregateRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchAggregates(ORG_ID).then((rows) => {
      if (!active) return;
      setAggregates(rows);
      setBuckets(harvestBuckets(rows));
      setError(null);
    }).catch((reason: unknown) => {
      if (active) setError(isServerError(reason) ? reason.message : "Timeline data is unavailable.");
    });
    return () => { active = false; };
  }, []);

  if (error) return <Alert tone="error" title="Timeline unavailable">{error}</Alert>;
  if (buckets === null) return <Skeleton label="Loading timeline" />;
  const crops = ["All", ...new Set(aggregates.map((row) => row.cropCode))];
  const rows = (cropF === "All" ? aggregates : aggregates.filter((row) => row.cropCode === cropF));
  return (
    <section aria-labelledby="timeline-h">
      <h2 id="timeline-h">Timeline</h2>
      <div className="filters" role="search" aria-label="Filter timeline">
        <Select name="tl-crop" label="Crop" options={crops} value={cropF}
          onChange={(event) => setCropF(event.target.value)} />
      </div>
      <BarChart
        title="Planned area by harvest period"
        unit="ha"
        bars={buckets.map((bucket) => ({ label: bucket.period, value: bucket.areaHa }))}
        emptyNote="No planned area"
      />
      <h3>Period agenda</h3>
      <DataTable
        caption="Planned area and production by crop and period"
        columns={["Crop", "Period", "Area", "Production"]}
        rows={rows.map((row) => [
          row.cropCode,
          row.harvestPeriod,
          `${row.plannedAreaHa} ha`,
          row.estimatedProductionMt === null ? "Yield unavailable" : `${row.estimatedProductionMt} MT`,
        ])}
      />
      {rows.length === 0 && <EmptyState title="No periods in this filter" body="Change the crop filter to see timeline rows." />}
    </section>
  );
}

function ContextCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section aria-label={title}>
      <h3>{title}</h3>
      {children}
    </section>
  );
}

export function ClimateCard({ geography }: { geography: string }) {
  const [points, setPoints] = useState<ClimatePoint[] | null>(null);

  useEffect(() => {
    let active = true;
    fetchClimate(geography).then((rows) => {
      if (active) setPoints(rows);
    }).catch(() => {
      if (active) setPoints([]);
    });
    return () => { active = false; };
  }, [geography]);

  if (points === null) return <Skeleton label="Loading climate context" />;
  if (points.length === 0) {
    return (
      <ContextCard title="Climate context">
        <p role="status">Climate context is not available right now. Coordination results do not depend on it.</p>
      </ContextCard>
    );
  }
  return (
    <ContextCard title="Climate context">
      <ul className="cards">
        {points.map((point, index) => (
          <li key={`${point.period}-${index}`}>
            <article className="card" aria-label={`Climate outlook ${point.period}`}>
              <h3>{point.period}</h3>
              <p>{point.outlook}</p>
              <p className="hint">{point.source} · {point.sourceDate} · {point.geography}</p>
            </article>
          </li>
        ))}
      </ul>
    </ContextCard>
  );
}

export function WeatherCard({ geography }: { geography: string }) {
  const [weather, setWeather] = useState<WeatherPoint | "missing" | null>(null);

  useEffect(() => {
    let active = true;
    fetchWeatherSnapshot(geography).then((result) => {
      if (active) setWeather(result ?? "missing");
    }).catch(() => {
      if (active) setWeather("missing");
    });
    return () => { active = false; };
  }, [geography]);

  if (weather === null) return <Skeleton label="Loading weather context" />;
  if (weather === "missing") {
    return (
      <ContextCard title="Weather context">
        <p role="status">Weather context is not available right now. Your coordination result does not depend on it.</p>
      </ContextCard>
    );
  }
  return (
    <ContextCard title="Weather context">
      <p>{weather.summary}</p>
      <p className="hint">{weather.source} · {weather.retrievedAt} · {weather.geography}</p>
      <p className="hint">Short-term context only. No invented observations are shown.</p>
    </ContextCard>
  );
}

export function SuitabilityCard({ cropCode, geography }: { cropCode: string; geography: string }) {
  const [points, setPoints] = useState<SuitabilityPoint[] | null>(null);

  useEffect(() => {
    let active = true;
    fetchSuitability(cropCode).then((rows) => {
      if (!active) return;
      setPoints(rows.filter((row) => row.geography === geography || geography === ""));
    }).catch(() => {
      if (active) setPoints([]);
    });
    return () => { active = false; };
  }, [cropCode, geography]);

  if (points === null) return <Skeleton label="Loading suitability context" />;
  if (points.length === 0) {
    return (
      <ContextCard title="Suitability context">
        <p role="status">No suitability layer covers this crop and place yet.</p>
      </ContextCard>
    );
  }
  return (
    <ContextCard title="Suitability context">
      <ul className="cards">
        {points.map((point) => (
          <li key={point.layerId}>
            <article className="card" aria-label={`Suitability ${point.suitabilityClass}`}>
              <h3>{point.suitabilityClass}</h3>
              <p className="hint">{point.source} · Layer {point.layerId} · {point.geography}</p>
              <p>Suitability is contextual information, not an automatic planting recommendation.</p>
            </article>
          </li>
        ))}
      </ul>
    </ContextCard>
  );
}

export function YieldCard({ cropCode, geography }: { cropCode: string; geography: string }) {
  const [yieldPoint, setYieldPoint] = useState<YieldPoint | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    fetchCropYield(cropCode, geography).then((result) => {
      if (active) setYieldPoint(result);
    }).catch(() => {
      if (active) setError(true);
    });
    return () => { active = false; };
  }, [cropCode, geography]);

  if (error) {
    return (
      <ContextCard title="Yield reference">
        <p role="status">Yield evidence unavailable for this crop and place. No production estimate is inferred.</p>
      </ContextCard>
    );
  }
  if (yieldPoint === null) return <Skeleton label="Loading yield reference" />;
  return (
    <ContextCard title="Yield reference">
      {yieldPoint.yieldMtPerHa === null ? (
        <p role="status">Yield evidence unavailable for this crop and place. No production estimate is inferred.</p>
      ) : (
        <p>{yieldPoint.yieldMtPerHa} MT per ha in {yieldPoint.geography}.</p>
      )}
    </ContextCard>
  );
}

export function AttentionStatus({ stale }: { stale: boolean }) {
  return <Status label={stale ? "Stale evidence" : "Evidence current"} tone={stale ? "warn" : "ok"} />;
}
