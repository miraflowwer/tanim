// Farmer views: F1 Home, F2 New Plan, F3 Result, F4 Adjust, F5 My Plans.
// Trusted coordination results come from FastAPI. Offline mode renders only the
// committed synthetic snapshot; it never recalculates GRCI in the browser.
import { useEffect, useRef, useState } from "react";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { ClimateContext, PriceContext } from "../components/Context";
import { DateField } from "../components/DateField";
import { Dialog } from "../components/Dialog";
import { EmptyState } from "../components/EmptyState";
import { NumberField } from "../components/NumberField";
import { Select } from "../components/Select";
import { Skeleton } from "../components/Skeleton";
import { Status } from "../components/Status";
import { TextField } from "../components/TextField";
import { calculatePlan, clearSession, createFarm, createPlan, isServerError, signIn, updatePlan } from "../lib/api";
import {
  EMPTY_HOME,
  IDENTITIES_HIDDEN,
  ORG_NAME,
  ORG_SCOPE,
  STATUS_LABEL,
  SYNTHETIC_BADGE,
} from "../lib/copy";
import { CROPS, ORG_ID } from "../lib/store";
import {
  ERROR_COPY,
  type ApiPlanResource,
  type CalculateResponse,
  type ClimateCtx,
  type NewPlanInput,
  type Plan,
  type PriceObs,
} from "../types";

const UI_PLAN_STATUS = {
  draft: "Draft", planned: "Planned", harvested: "Harvested", cancelled: "Cancelled",
} satisfies Record<ApiPlanResource["status"], Plan["state"]>;

export interface FarmerCtx {
  plans: Plan[];
  prices: PriceObs[];
  climate: ClimateCtx;
  onSavePlan: (plan: Plan, result?: CalculateResponse) => void;
  onUpdatePlan: (plan: Plan, result: CalculateResponse) => void;
}

export function Home({ plans }: { plans: Plan[] }) {
  const mine = plans.filter((p) => p.state === "Planned" || p.state === "Draft");
  const upcoming = [...plans]
    .filter((p) => p.state === "Planned")
    .sort((a, b) => a.harvestPeriod.localeCompare(b.harvestPeriod))
    .slice(0, 3);
  return (
    <section aria-labelledby="home-h">
      <h2 id="home-h">What needs your attention?</h2>
      <p className="hint">{ORG_NAME} · {ORG_SCOPE}</p>
      <p><Button onClick={() => (location.hash = "#/plans/new")}>Create planting plan</Button></p>
      {mine.length === 0 ? (
        <EmptyState title={EMPTY_HOME} actionLabel="Create planting plan" onAction={() => (location.hash = "#/plans/new")} />
      ) : (
        <ul className="cards">
          {mine.map((p) => (
            <li key={p.id}>
              <Card title={`${p.crop} · ${p.harvestPeriod}`}>
                {p.synthetic ? <p className="badge" role="note">Synthetic plan snapshot</p>
                  : <Status label="API plan — open result to check" tone="info" />}
                <p>{p.areaHa} ha · {p.farm}</p>
                <p className="hint">Updated {p.updatedAt} · {p.state}</p>
                <p><a href={`#/result/${p.id}`}>View coordination result</a></p>
              </Card>
            </li>
          ))}
        </ul>
      )}
      <section aria-labelledby="upcoming-h">
        <h3 id="upcoming-h">Upcoming harvest</h3>
        {upcoming.length === 0 ? <p className="hint">No planned harvests yet.</p> : (
          <ul className="cards">
            {upcoming.map((p) => (
              <li key={p.id}>
                <Card title={`${p.crop} · ${p.harvestPeriod}`}>
                  <p>{p.areaHa} ha · {p.farm}</p>
                  <p><a href={`#/plans/${p.id}`}>Open plan</a></p>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </section>
      <p className="hint">Your group sees totals, not your private details, unless you allow it.</p>
    </section>
  );
}

type FieldName = "cropCode" | "farm" | "areaHa" | "marginHa" | "plantingDate" | "harvestPeriod";
type FieldErrors = Partial<Record<FieldName, string>>;

function validate(input: NewPlanInput): FieldErrors {
  const errors: FieldErrors = {};
  const crop = CROPS.find((c) => c.code === input.cropCode);
  if (!crop || !crop.supported) errors.cropCode = ERROR_COPY.CROP_UNSUPPORTED;
  if (!input.farm.trim()) errors.farm = "Enter the farm or location name.";
  if (!(input.areaHa > 0)) errors.areaHa = "Planned area must be more than 0 ha.";
  if (!(input.marginHa >= 0)) errors.marginHa = "Uncertainty must be 0 or more.";
  if (!input.plantingDate) errors.plantingDate = "Enter the planting date.";
  if (!input.harvestPeriod) errors.harvestPeriod = "Enter the expected harvest period (for example 2026-Q4).";
  return errors;
}

const DRAFT_KEY = "tanim-newplan-draft";

function loadDraft(): NewPlanInput {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (raw) return JSON.parse(raw) as NewPlanInput;
  } catch {
    /* ignore corrupt draft */
  }
  return {
    cropCode: "tomato",
    farm: "",
    areaHa: 1,
    marginHa: 0,
    plantingDate: "2026-09-20",
    harvestPeriod: "2026-Q4",
  };
}

const API_FIELD_TO_UI: Record<string, FieldName> = {
  crop_code: "cropCode",
  organization_id: "farm",
  area_ha: "areaHa",
  area_margin_ha: "marginHa",
  planting_date: "plantingDate",
  harvest_period: "harvestPeriod",
};

export function NewPlan({ onSavePlan }: { onSavePlan: FarmerCtx["onSavePlan"] }) {
  const [input, setInput] = useState<NewPlanInput>(loadDraft);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [serverNote, setServerNote] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const summaryRef = useRef<HTMLDivElement>(null);
  const errorCount = Object.keys(errors).length;

  useEffect(() => {
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(input));
    } catch {
      /* storage full or blocked */
    }
  }, [input]);

  useEffect(() => {
    if (errorCount > 0) summaryRef.current?.focus();
  }, [errorCount]);

  function set<K extends keyof NewPlanInput>(key: K, value: NewPlanInput[K]) {
    setInput((prev) => ({ ...prev, [key]: value }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const localErrors = validate(input);
    setErrors(localErrors);
    setServerNote(null);
    if (Object.keys(localErrors).length > 0) return;

    const crop = CROPS.find((c) => c.code === input.cropCode);
    if (!crop) return;
    const plan: Plan = {
      id: `offline-${Date.now()}`,
      crop: crop.name,
      cropCode: crop.code,
      farm: input.farm.trim(),
      areaHa: input.areaHa,
      marginHa: input.marginHa,
      plantingDate: input.plantingDate,
      harvestPeriod: input.harvestPeriod.trim(),
      state: "Draft",
      updatedAt: new Date().toISOString().slice(0, 10),
      scope: ORG_SCOPE,
    };

    setSaving(true);
    try {
      const farm = await createFarm(ORG_ID, input.farm.trim());
      const saved = await createPlan({ ...input, organizationId: ORG_ID, farmId: farm.id });
      const result = await calculatePlan(saved.id, {
        crop: plan.crop,
        harvestPeriod: plan.harvestPeriod,
      });
      onSavePlan({ ...plan, id: saved.id, state: UI_PLAN_STATUS[saved.status] }, result);
      location.hash = `#/result/${saved.id}`;
    } catch (error: unknown) {
      if (isServerError(error) && error.status !== 0) {
        if (error.code === "VALIDATION_ERROR" && error.field) {
          const field = API_FIELD_TO_UI[error.field];
          if (field) {
            setErrors({ [field]: error.message });
            return;
          }
        }
        setServerNote(error.message);
        return;
      }
      const message = isServerError(error) ? error.message : ERROR_COPY.SERVICE_UNAVAILABLE;
      setServerNote(message);
      // Keep the draft in localStorage. A new plan has no trusted offline result.
      // Only the exact committed seeded plan may display a synthetic snapshot.
    } finally {
      setSaving(false);
    }
  }

  return (
    <section aria-labelledby="new-h">
      <h2 id="new-h">New planting plan</h2>
      {errorCount > 0 && (
        <div ref={summaryRef} tabIndex={-1} role="alert" aria-labelledby="err-sum-h" className="err-summary">
          <h3 id="err-sum-h">Check the highlighted fields</h3>
          <ul>{(Object.keys(errors) as FieldName[]).map((key) => (
            <li key={key}><a href={`#${key}`}>{errors[key]}</a></li>
          ))}</ul>
        </div>
      )}
      <form onSubmit={onSubmit} noValidate>
        <Select name="cropCode" label="Crop" options={CROPS.map((c) => c.code)} value={input.cropCode}
          error={errors.cropCode} onChange={(e) => set("cropCode", e.target.value)} />
        <TextField name="farm" label="Farm or location" placeholder="e.g. Brgy. San Isidro" value={input.farm}
          error={errors.farm} onChange={(e) => set("farm", e.target.value)} />
        <NumberField name="areaHa" label="Planned area (ha)" min={0} step={0.1} value={String(input.areaHa)}
          error={errors.areaHa} onChange={(e) => set("areaHa", Number(e.target.value))} />
        <NumberField name="marginHa" label="Area uncertainty ± (ha, optional)" min={0} step={0.1} value={String(input.marginHa)}
          error={errors.marginHa} onChange={(e) => set("marginHa", Number(e.target.value))} />
        <DateField name="plantingDate" label="Planting date" value={input.plantingDate}
          error={errors.plantingDate} onChange={(e) => set("plantingDate", e.target.value)} />
        <TextField name="harvestPeriod" label="Expected harvest period" placeholder="e.g. 2026-Q4" value={input.harvestPeriod}
          error={errors.harvestPeriod} onChange={(e) => set("harvestPeriod", e.target.value)} />
        {saving ? <Skeleton label="Saving plan…" /> : <Button type="submit">Save plan</Button>}
        <p className="hint">The system finds the reviewed comparison for you. You do not need to enter demand amounts.</p>
      </form>
      {serverNote && <Alert tone="error" title="Server notice">{serverNote}</Alert>}
    </section>
  );
}

function toneFor(status: CalculateResponse["coordinationStatus"]): "ok" | "warn" | "bad" | "info" {
  switch (status) {
    case "low_coordination_load": return "ok";
    case "elevated_coordination_load": return "warn";
    case "high_coordination_load": return "bad";
    case "historical_baseline_only": return "warn";
    case "more_evidence_needed": return "info";
  }
}

export function ResultView({
  plan, result, prices, climate,
}: {
  plan: Plan;
  result?: CalculateResponse;
  prices: PriceObs[];
  climate: ClimateCtx;
}) {
  const price = prices.find((item) => item.cropCode === plan.cropCode) ?? null;
  if (!result) {
    return (
      <section aria-labelledby="res-h" aria-live="polite">
        <h2 id="res-h">Coordination result</h2>
        <Alert tone="error" title="Result unavailable">
          TANIM has no server result or committed synthetic snapshot for this plan.
        </Alert>
      </section>
    );
  }

  return (
    <section aria-labelledby="res-h" aria-live="polite">
      <h2 id="res-h">Coordination result</h2>
      {result.synthetic && <p className="badge" role="note">{SYNTHETIC_BADGE}</p>}
      {result.stale && <Alert title="Stale evidence">{ERROR_COPY.STALE_EVIDENCE}</Alert>}

      <Card title="Result summary">
        <Status label={STATUS_LABEL[result.coordinationStatus]} tone={toneFor(result.coordinationStatus)} />
        <dl>
          <dt>Planned area</dt><dd>{result.plannedAreaHa} ha</dd>
          <dt>Expected production</dt><dd>{result.estimatedProductionMt} MT</dd>
          <dt>Reference used</dt><dd>{result.referenceUsed}</dd>
        </dl>
        <p>{result.headline}</p>
      </Card>

      <details className="card">
        <summary>Comparison detail</summary>
        {result.comparisonAmountMt === null ? (
          <p>{ERROR_COPY.COMPARISON_UNAVAILABLE}</p>
        ) : (
          <dl>
            <dt>Comparison amount</dt><dd>{result.comparisonAmountMt} MT</dd>
            <dt>Supply load</dt><dd>{result.supplyLoad ?? "—"}</dd>
            <dt>Uncertainty range</dt><dd>{result.estimatedRangeMt.low}–{result.estimatedRangeMt.high} MT</dd>
            <dt>Evidence quality</dt><dd>{result.evidenceQuality}</dd>
          </dl>
        )}
      </details>

      <Dialog triggerLabel="View detailed evidence" title="Detailed evidence">
        <dl>
          <dt>Reference type</dt><dd>{result.provenance.referenceType}</dd>
          <dt>Source</dt><dd>{result.provenance.source}</dd>
          <dt>Geography</dt><dd>{result.provenance.geography}</dd>
          <dt>Source period</dt><dd>{result.provenance.sourcePeriod}</dd>
          <dt>Verified at</dt><dd>{result.provenance.verifiedAt ?? "Not supplied"}</dd>
          <dt>Policy version</dt><dd>{result.provenance.calculationPolicyVersion}</dd>
          <dt>Engine version</dt><dd>{result.provenance.engineVersion}</dd>
          <dt>Evidence note</dt><dd>{result.provenance.evidenceNote}</dd>
        </dl>
      </Dialog>

      <section aria-labelledby="alt-h">
        <h3 id="alt-h">Other crops with available coordination evidence</h3>
        <p className="hint">
          The browser does not rank crops. Alternative coordination results appear after the API returns
          a reviewed result for that crop and period.
        </p>
      </section>

      <PriceContext price={price} />
      <ClimateContext climate={climate} />
      {plan.synthetic ? <p className="hint">This fixed synthetic plan is read only. Create an API plan to make an adjustment.</p>
        : <p><a href={`#/adjust/${plan.id}`}>Adjust this plan</a></p>}
    </section>
  );
}

export function AdjustView({ plan, onUpdatePlan }: { plan: Plan; onUpdatePlan: FarmerCtx["onUpdatePlan"] }) {
  const [area, setArea] = useState(plan.areaHa);
  const [planting, setPlanting] = useState(plan.plantingDate);
  const [period, setPeriod] = useState(plan.harvestPeriod);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [serverNote, setServerNote] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const summaryRef = useRef<HTMLDivElement>(null);
  const changed = area !== plan.areaHa || planting !== plan.plantingDate || period !== plan.harvestPeriod;

  if (plan.synthetic) return (
    <section aria-labelledby="adj-h">
      <h2 id="adj-h">Adjust plan</h2>
      <Alert title="Read-only synthetic plan">Create an API plan to save a new revision.</Alert>
      <p><a href="#/new">Create planting plan</a></p>
    </section>
  );

  async function save() {
    const next: NewPlanInput = {
      cropCode: plan.cropCode,
      farm: plan.farm,
      areaHa: area,
      marginHa: plan.marginHa,
      plantingDate: planting,
      harvestPeriod: period,
    };
    const nextErrors = validate(next);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      summaryRef.current?.focus();
      return;
    }
    setServerNote(null);
    setSaving(true);
    try {
      const saved = await updatePlan(plan.id, { areaHa: area, plantingDate: planting, harvestPeriod: period });
      const result = await calculatePlan(saved.id, { crop: plan.crop, harvestPeriod: period });
      onUpdatePlan({ ...plan, areaHa: saved.areaHa, plantingDate: saved.plantingDate,
        harvestPeriod: period, updatedAt: new Date().toISOString().slice(0, 10) }, result);
      location.hash = `#/result/${saved.id}`;
    } catch (error: unknown) {
      setServerNote(isServerError(error) ? error.message : ERROR_COPY.SERVICE_UNAVAILABLE);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section aria-labelledby="adj-h">
      <h2 id="adj-h">Adjust plan</h2>
      {Object.keys(errors).length > 0 && (
        <div ref={summaryRef} tabIndex={-1} role="alert" className="err-summary">
          <strong>Check the highlighted fields.</strong>
        </div>
      )}
      <NumberField name="area" label="Planned area (ha)" min={0} step={0.1} value={String(area)}
        error={errors.areaHa} onChange={(e) => setArea(Number(e.target.value))} />
      <DateField name="planting" label="Planting date" value={planting}
        error={errors.plantingDate} onChange={(e) => setPlanting(e.target.value)} />
      <TextField name="period" label="Expected harvest period" value={period}
        error={errors.harvestPeriod} onChange={(e) => setPeriod(e.target.value)} />
      <Alert title="Recalculation">
        Save changes to send the new revision to the API. The result page only displays the returned API result or a labeled snapshot.
      </Alert>
      <p><Button onClick={save} disabled={!changed || saving}>{saving ? "Saving…" : "Save changes"}</Button></p>
      {serverNote && <Alert tone="error" title="Server notice">{serverNote}</Alert>}
    </section>
  );
}

const GROUPS: Plan["state"][] = ["Draft", "Planned", "Harvested", "Cancelled"];

export function MyPlans({ plans }: { plans: Plan[] }) {
  const [search, setSearch] = useState("");
  const [crop, setCrop] = useState("");
  const [status, setStatus] = useState("");
  const query = search.trim().toLowerCase();
  const activeFilters = [crop, status, query].filter(Boolean).length;
  const filtered = plans.filter((p) => {
    if (crop && p.cropCode !== crop) return false;
    if (status && p.state !== status) return false;
    if (query && !`${p.crop} ${p.farm} ${p.harvestPeriod}`.toLowerCase().includes(query)) return false;
    return true;
  });
  return (
    <section aria-labelledby="my-h">
      <h2 id="my-h">My Plans</h2>
      <p><Button onClick={() => (location.hash = "#/plans/new")}>New planting plan</Button></p>
      <form role="search" aria-label="Filter plans" onSubmit={(e) => e.preventDefault()}>
        <TextField name="plan-search" label="Search plans" placeholder="Crop, farm, or harvest period"
          value={search} onChange={(e) => setSearch(e.target.value)} />
        <div className="row">
          <Select name="crop" label="Crop" options={["", ...CROPS.map((c) => c.code)]} value={crop}
            onChange={(e) => setCrop(e.target.value)} />
          <Select name="status" label="Status" options={["", ...GROUPS]} value={status}
            onChange={(e) => setStatus(e.target.value)} />
        </div>
        <p className="hint">
          {activeFilters > 0 ? `${activeFilters} filter${activeFilters > 1 ? "s" : ""} active. ` : ""}
          {activeFilters > 0 && <button type="button" className="linklike" onClick={() => { setSearch(""); setCrop(""); setStatus(""); }}>Clear filters</button>}
        </p>
      </form>
      {GROUPS.map((group) => {
        const items = filtered.filter((p) => p.state === group);
        if (status && group !== status) return null;
        return (
          <section key={group} aria-labelledby={`my-${group}`}>
            <h3 id={`my-${group}`}>{group}</h3>
            {items.length === 0 ? <p className="hint">No {group.toLowerCase()} plans.</p> : (
              <ul className="cards">
                {items.map((p) => (
                  <li key={p.id}>
                    <Card title={`${p.crop} · ${p.areaHa} ha · ${p.harvestPeriod}`}>
                      <p>{p.crop} · {p.areaHa} ha · {p.harvestPeriod} · {p.state}</p>
                      {p.synthetic && <p className="badge" role="note">Synthetic plan snapshot</p>}
                      <p className="hint">Updated {p.updatedAt}</p>
                      <p><a href={`#/result/${p.id}`}>View result</a>
                        {!p.synthetic && <> · <a href={`#/adjust/${p.id}`}>Adjust</a></>}</p>
                    </Card>
                  </li>
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </section>
  );
}

export function Profile() {
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function demoSignIn(userId: string) {
    setBusy(true);
    setNotice(null);
    try {
      await signIn(userId);
      setNotice(`Signed in as ${userId} for the development API.`);
    } catch (error: unknown) {
      setNotice(isServerError(error) ? error.message : ERROR_COPY.SERVICE_UNAVAILABLE);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-labelledby="prof-h">
      <h2 id="prof-h">Profile</h2>
      <Card title="Farmer record">
        <p>Organization: {ORG_NAME}</p>
        <p className="hint">{IDENTITIES_HIDDEN}</p>
      </Card>
      <Card title="Development API session">
        <p className="hint">These identities work only when the API explicitly enables development authentication. The server verifies every request.</p>
        <p><Button disabled={busy} onClick={() => demoSignIn("farmer-1")}>Sign in as demo farmer</Button></p>
        <p><Button disabled={busy} onClick={() => demoSignIn("reviewer-1")}>Sign in as demo reviewer</Button></p>
        <p><Button onClick={() => { clearSession(); setNotice("Signed out of the development API."); }}>Sign out</Button></p>
        {notice && <p role="status" aria-live="polite">{notice}</p>}
      </Card>
    </section>
  );
}
