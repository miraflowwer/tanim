// Plan detail (§07): Summary / History / Calculations tabs. Historical
// provenance is preserved — a new revision never rewrites an old one.
import { useEffect, useState } from "react";
import { Alert } from "../../components/Alert";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { Skeleton } from "../../components/Skeleton";
import { Status } from "../../components/Status";
import { Breadcrumbs, PageHeader } from "../../components/layout/Shell";
import { cancelPlan, fetchPlan, fetchRevisions, isServerError, toCalculationRuns } from "../../lib/api";
import type { ApiPlanResource, CalculateResponse, PlanRevision } from "../../types";

type Tab = "summary" | "history" | "calculations";

export function PlanDetail({ planId, latest }: { planId: string; latest?: CalculateResponse }) {
  const [plan, setPlan] = useState<ApiPlanResource | null>(null);
  const [revisions, setRevisions] = useState<PlanRevision[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("summary");
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    Promise.all([fetchPlan(planId), fetchRevisions(planId).catch(() => null)]).then(([row, revs]) => {
      if (!active) return;
      setPlan(row);
      setRevisions(revs);
    }).catch((reason: unknown) => {
      if (active) setError(isServerError(reason) ? reason.message : "The plan service is unavailable.");
    });
    return () => { active = false; };
  }, [planId]);
  async function cancel() {
    if (!window.confirm("Cancel this plan? History is preserved.")) return;
    try {
      await cancelPlan(planId);
      setPlan((p) => (p ? { ...p, status: "cancelled" } : p));
      setNotice("Plan cancelled. History is preserved.");
    } catch (reason: unknown) {
      setNotice(isServerError(reason) ? reason.message : "The plan service is unavailable.");
    }
  }
  if (error) {
    return (
      <section aria-labelledby="pd-h">
        <h2 id="pd-h">Planting plan</h2>
        <Alert tone="error" title="Plan unavailable">{error}</Alert>
        <p><a href="#/plans">Back to My Plans</a></p>
      </section>
    );
  }
  if (!plan) return <section aria-label="Loading plan"><Skeleton label="Loading plan…" /></section>;
  const runs = toCalculationRuns(revisions ?? [], latest);
  return (
    <section aria-labelledby="pd-h">
      <Breadcrumbs trail={[{ label: "Plans", href: "#/plans" }, { label: `${plan.cropCode} · ${plan.harvestPeriod}` }]} />
      <PageHeader title={`${plan.cropCode} · ${plan.harvestPeriod}`}
        purpose={`Revision ${plan.revisionNumber} · ${plan.status}`}
        action={<Button onClick={() => (location.hash = `#/plans/${plan.id}/result`)}>View result</Button>} />
      <h2 id="pd-h" className="visually-hidden">Planting plan</h2>
      <div className="tabs" role="tablist" aria-label="Plan sections">
        {(["summary", "history", "calculations"] as Tab[]).map((t) => (
          <button key={t} type="button" role="tab" aria-selected={tab === t}
            className={tab === t ? undefined : "secondary"} onClick={() => setTab(t)}>
            {t === "summary" ? "Summary" : t === "history" ? "History" : "Calculations"}
          </button>
        ))}
      </div>
      {tab === "summary" && (
        <Card title="Summary">
          <dl>
            <dt>Crop</dt><dd>{plan.cropCode}</dd>
            <dt>Area</dt><dd>{plan.areaHa} ha ± {plan.areaMarginHa} ha</dd>
            <dt>Planting date</dt><dd>{plan.plantingDate}</dd>
            <dt>Harvest period</dt><dd>{plan.harvestPeriod}</dd>
            <dt>Status</dt><dd><Status label={plan.status} tone={plan.status === "cancelled" ? "bad" : "info"} /></dd>
          </dl>
          <p className="row">
            <Button variant="secondary" onClick={() => (location.hash = `#/plans/${plan.id}/adjust`)}>Adjust plan</Button>
            {plan.status !== "cancelled" && plan.status !== "harvested" && (
              <Button variant="secondary" onClick={cancel}>Cancel plan</Button>
            )}
          </p>
          {notice && <p role="status">{notice}</p>}
          {latest && <p className="hint">{latest.headline}</p>}
        </Card>
      )}
      {tab === "history" && (
        <div>
          {revisions === null && <p className="hint">Revision history is unavailable offline. The plan summary above is current.</p>}
          {revisions !== null && revisions.length === 0 && <p className="hint">No revisions recorded.</p>}
          {revisions !== null && revisions.length > 0 && (
            <ul className="cards">
              {[...revisions].reverse().map((rev) => (
                <li key={rev.revisionNumber}>
                  <Card title={`Revision ${rev.revisionNumber}`}>
                    <p>{rev.areaHa} ha ± {rev.areaMarginHa} ha · planted {rev.plantingDate} · harvest {rev.harvestPeriod}</p>
                    <p className="hint">{rev.createdAt || "date not recorded"}</p>
                  </Card>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {tab === "calculations" && (
        <div>
          {runs.length === 0 && <p className="hint">No calculation runs recorded for this plan yet.</p>}
          <ul className="cards">
            {runs.map((run) => (
              <li key={run.calculationId}>
                <Card title={`Revision ${run.revisionNumber}`}>
                  <p>{run.coordinationState}</p>
                  <p className="hint">{run.expectedProductionMt !== null ? `${run.expectedProductionMt} MT` : "No production estimate"} · policy {run.policyVersion} · engine {run.engineVersion}</p>
                </Card>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="hint"><a href="#/plans">Back to My Plans</a> · <a href={`#/plans/${plan.id}/result`}>Result</a></p>
    </section>
  );
}
