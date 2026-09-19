// Coordinator screens render FastAPI aggregates and reviewed reference records.
// Offline tables are fixed synthetic snapshots and cannot create trusted results.
import { useEffect, useState } from "react";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { ClimateContext, PriceContext } from "../components/Context";
import { DataTable } from "../components/DataTable";
import { Select } from "../components/Select";
import { Status } from "../components/Status";
import { TextField } from "../components/TextField";
import { fetchAggregates, isServerError } from "../lib/api";
import { IDENTITIES_HIDDEN, REVIEWER_ONLY, STALE_BANNER } from "../lib/copy";
import { ORG_ID } from "../lib/store";
import type {
  AggregateRow, ClimateCtx, DataSourceRow, Plan, PriceObs,
  ReferenceRecord, RefWorkflow, Role,
} from "../types";

interface OverviewRow {
  crop: string;
  period: string;
  farmers: number;
  area: number;
  production: number | null;
  state: string;
  scope: string;
}

const SYNTHETIC_OVERVIEW: OverviewRow[] = [
  { crop: "Tomato", period: "2026-Q4", farmers: 1, area: 12.5, production: null,
    state: "Synthetic snapshot", scope: "CALABARZON" },
  { crop: "Eggplant", period: "2026-Q4", farmers: 1, area: 2, production: null,
    state: "Synthetic snapshot", scope: "CALABARZON" },
];

function apiRows(rows: AggregateRow[]): OverviewRow[] {
  return rows.map((row) => ({
    crop: row.cropCode,
    period: row.harvestPeriod,
    farmers: row.farmers,
    area: row.plannedAreaHa,
    production: row.estimatedProductionMt,
    state: row.estimatedProductionMt === null ? "Yield evidence needed" : "API aggregate",
    scope: "Organization scope",
  }));
}

export function Overview() {
  const [rows, setRows] = useState<OverviewRow[]>(SYNTHETIC_OVERVIEW);
  const [snapshot, setSnapshot] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cropF, setCropF] = useState("All");
  const [periodF, setPeriodF] = useState("All");
  const [locF, setLocF] = useState("All");
  const [statusF, setStatusF] = useState("All");

  useEffect(() => {
    let active = true;
    fetchAggregates(ORG_ID).then((result) => {
      if (!active) return;
      setRows(apiRows(result));
      setSnapshot(false);
      setError(null);
    }).catch((reason: unknown) => {
      if (active) setError(isServerError(reason) ? reason.message : "The aggregate API is unavailable.");
    });
    return () => { active = false; };
  }, []);

  const crops = ["All", ...new Set(rows.map((row) => row.crop))];
  const periods = ["All", ...new Set(rows.map((row) => row.period))];
  const locs = ["All", ...new Set(rows.map((row) => row.scope))];
  const states = ["All", ...new Set(rows.map((row) => row.state))];
  const filtered = rows.filter((row) =>
    (cropF === "All" || row.crop === cropF) &&
    (periodF === "All" || row.period === periodF) &&
    (locF === "All" || row.scope === locF) &&
    (statusF === "All" || row.state === statusF)
  );
  return (
    <section aria-labelledby="ov-h">
      <h2 id="ov-h">What is our group planning to produce, and when?</h2>
      {snapshot && <p role="note" className="badge">Synthetic offline aggregate snapshot. Values are fixed demo data.</p>}
      {error && <Alert tone="error" title="Aggregate API unavailable">{error}</Alert>}
      <div className="filters" role="search" aria-label="Filter overview">
        <Select name="f-crop" label="Crop" options={crops} value={cropF} onChange={(event) => setCropF(event.target.value)} />
        <Select name="f-period" label="Harvest period" options={periods} value={periodF} onChange={(event) => setPeriodF(event.target.value)} />
        <Select name="f-loc" label="Location" options={locs} value={locF} onChange={(event) => setLocF(event.target.value)} />
        <Select name="f-status" label="Status" options={states} value={statusF} onChange={(event) => setStatusF(event.target.value)} />
      </div>
      <DataTable
        caption={`${filtered.length} of ${rows.length} groups shown`}
        columns={["Crop", "Harvest period", "Farmers", "Planned area", "Estimated production", "Coordination state"]}
        rows={filtered.map((row) => [
          row.crop, row.period, String(row.farmers), `${row.area} ha`,
          row.production === null ? (snapshot ? "API result required" : "Yield unavailable") : `${row.production} MT`,
          row.state,
        ])}
      />
      {filtered.length === 0 && <p className="hint">No groups match these filters.</p>}
    </section>
  );
}

export function PlansList({ plans }: { plans: Plan[] }) {
  const [q, setQ] = useState("");
  const filtered = plans.filter((plan) =>
    q.trim() === "" || `${plan.crop} ${plan.harvestPeriod} ${plan.farm} ${plan.state}`.toLowerCase().includes(q.toLowerCase())
  );
  return (
    <section aria-labelledby="plans-h">
      <h2 id="plans-h">Plans</h2>
      <p role="note" className="badge">Seeded plans are synthetic snapshots. New plans use the API.</p>
      <TextField name="q" label="Filter by crop, harvest period, location, status" value={q}
        onChange={(event) => setQ(event.target.value)} placeholder="e.g. Tomato" />
      <DataTable columns={["Crop", "Period", "Location", "Area", "State"]}
        rows={filtered.map((plan) => [plan.crop, plan.harvestPeriod, plan.farm, `${plan.areaHa} ha`,
          plan.synthetic ? `${plan.state} (synthetic snapshot)` : plan.state])} />
    </section>
  );
}

export function CropDetail({
  cropCode, cropName, prices, climate,
}: {
  cropCode: string;
  cropName: string;
  prices: PriceObs[];
  climate: ClimateCtx;
}) {
  const [row, setRow] = useState<AggregateRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    fetchAggregates(ORG_ID).then((rows) => {
      if (active) setRow(rows.find((candidate) => candidate.cropCode === cropCode) ?? null);
    }).catch((reason: unknown) => {
      if (active) setError(isServerError(reason) ? reason.message : "The aggregate API is unavailable.");
    });
    return () => { active = false; };
  }, [cropCode]);
  return (
    <section aria-labelledby="cd-h">
      <h2 id="cd-h">{cropName} detail</h2>
      {error && <Alert tone="error" title="Aggregate API unavailable">{error}</Alert>}
      <Card title="Organization aggregate">
        {row ? (
          <dl>
            <dt>Planned area</dt><dd>{row.plannedAreaHa} ha</dd>
            <dt>Estimated production</dt><dd>{row.estimatedProductionMt === null ? "Yield unavailable" : `${row.estimatedProductionMt} MT`}</dd>
            <dt>Contributing farmers</dt><dd>{row.farmers}</dd>
            <dt>Harvest timing</dt><dd>{row.harvestPeriod}</dd>
          </dl>
        ) : <p>API aggregate unavailable for this crop. No coordination classification is inferred.</p>}
      </Card>
      <section aria-labelledby="who-h">
        <h3 id="who-h">Contributors</h3>
        <p className="hint">{IDENTITIES_HIDDEN} Individual records require server authorization.</p>
      </section>
      <PriceContext price={prices.find((price) => price.cropCode === cropCode) ?? null} />
      <ClimateContext climate={climate} />
    </section>
  );
}

// These buttons are navigation affordances. FastAPI validates every transition.
const NEXT: Record<RefWorkflow, Array<"under_review" | "verified" | "rejected" | "draft" | "expired">> = {
  draft: ["under_review"],
  under_review: ["verified", "rejected"],
  rejected: ["draft"],
  verified: ["expired"],
  superseded: [],
  expired: [],
};

export function ReferencesView({
  refs, role, onTransition, error,
}: {
  refs: ReferenceRecord[];
  role: Role;
  onTransition: (id: string, next: "under_review" | "verified" | "rejected" | "draft" | "expired") => void;
  error: string | null;
}) {
  return (
    <section aria-labelledby="ref-h">
      <h2 id="ref-h">References</h2>
      {error && <Alert tone="error" title="Reference API notice">{error}</Alert>}
      <p className="hint">Verification is enforced by FastAPI. This screen displays the server review state.</p>
      <ul className="cards">
        {refs.map((reference) => (
          <li key={reference.id}>
            <article className="card" aria-label={`${reference.crop} reference ${reference.version}`}>
              <h3>{reference.crop} · {reference.amountMt} {reference.unit} · {reference.version}</h3>
              {reference.synthetic && <p role="note" className="badge">Synthetic offline reference. Read only.</p>}
              <dl>
                <dt>Reference type</dt><dd>{reference.referenceType}</dd>
                <dt>Geography</dt><dd>{reference.geography}</dd>
                <dt>Period</dt><dd>{reference.period}</dd>
                <dt>Source</dt><dd>{reference.source}</dd>
                <dt>Evidence note</dt><dd>{reference.evidenceNote}</dd>
                <dt>Reviewer</dt><dd>{reference.reviewer}</dd>
                <dt>Verification status</dt><dd>{reference.verificationStatus}</dd>
                <dt>Effective date</dt><dd>{reference.effectiveDate}</dd>
                <dt>Validity end</dt><dd>{reference.expiryState}</dd>
              </dl>
              <p className="hint">Review state: {reference.workflow}.</p>
              <p className="row">
                {NEXT[reference.workflow].map((next) => {
                  const reviewerAction = next !== "under_review";
                  const blocked = reference.synthetic || (reviewerAction && role !== "reviewer");
                  return (
                    <Button key={next} variant="secondary" disabled={blocked}
                      title={blocked ? REVIEWER_ONLY : undefined}
                      onClick={() => onTransition(reference.id, next)}>
                      {next === "under_review" ? "Submit for review"
                        : next === "verified" ? "Mark verified"
                        : next === "rejected" ? "Reject"
                        : next === "draft" ? "Reopen draft" : "Mark expired"}
                    </Button>
                  );
                })}
              </p>
              {role !== "reviewer" && !reference.synthetic && <p className="hint">{REVIEWER_ONLY}</p>}
            </article>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function DataHealth({ sources }: { sources: DataSourceRow[] }) {
  const anyStale = sources.some((source) => source.stale);
  return (
    <section aria-labelledby="data-h">
      <h2 id="data-h">Data health</h2>
      {anyStale && <Alert title="Stale source">{STALE_BANNER}</Alert>}
      <DataTable columns={["Source", "Last refresh", "Expected", "State", "Last error"]}
        rows={sources.map((source) => [source.source, source.lastRefresh, source.expected, source.state, source.lastError ?? "—"])} />
      <p className="hint"><Status label="Source states are shown as text, not color alone" tone="info" /></p>
    </section>
  );
}
