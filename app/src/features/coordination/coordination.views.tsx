import { useEffect, useState } from "react";
import { Alert } from "../../components/Alert";
import { Card } from "../../components/Card";
import { DataTable } from "../../components/DataTable";
import { EmptyState } from "../../components/EmptyState";
import { Skeleton } from "../../components/Skeleton";
import { Status } from "../../components/Status";
import { fetchAggregates, fetchReferences, isServerError } from "../../lib/api";
import { ORG_ID } from "../../lib/store";
import type { AggregateRow, ReferenceRecord } from "../../types";
import { fetchCoordinatorPlan, type CoordinatorPlanDetail } from "./coordination.api";
import { buildAttentionItems } from "./coordination.logic";

function severityTone(severity: string): "ok" | "warn" | "bad" | "info" {
  return severity === "high" ? "bad" : severity === "watch" ? "warn" : "info";
}

export function AttentionQueue() {
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
      if (active) setError(isServerError(reason) ? reason.message : "The attention data is unavailable.");
    });
    return () => { active = false; };
  }, []);

  if (error) return <Alert tone="error" title="Attention unavailable">{error}</Alert>;
  if (aggregates === null) return <Skeleton label="Loading attention items" />;
  const items = buildAttentionItems(aggregates, references);
  return (
    <section aria-labelledby="attention-h">
      <h2 id="attention-h">Attention</h2>
      <p className="hint">One next action per item. No farmer is blamed here.</p>
      {items.length === 0 ? (
        <EmptyState title="Nothing needs attention" body="Every crop and period currently has reviewed evidence and an estimate." />
      ) : (
        <ul className="cards">
          {items.map((item) => (
            <li key={item.id}>
              <article className="card" aria-label={`${item.crop} ${item.period}: ${item.reason}`}>
                <h3>{item.crop} · {item.period}</h3>
                <Status label={item.evidenceState} tone={severityTone(item.severity)} />
                <p>{item.reason}</p>
                <p className="hint">Geography: {item.geography}</p>
                <p><a href={item.nextHref}>{item.nextAction}</a></p>
              </article>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function CoordinatorPlanDetail({ planId }: { planId: string }) {
  const [detail, setDetail] = useState<CoordinatorPlanDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchCoordinatorPlan(planId).then((result) => {
      if (!active) return;
      setDetail(result);
      setError(null);
    }).catch((reason: unknown) => {
      if (active) setError("This plan is unavailable. It may not exist or you may lack access.");
      void reason;
    });
    return () => { active = false; };
  }, [planId]);

  if (error) return <Alert tone="error" title="Plan unavailable">{error}</Alert>;
  if (detail === null) return <Skeleton label="Loading plan detail" />;
  return (
    <section aria-labelledby="cplan-h">
      <h2 id="cplan-h">Plan {detail.id}</h2>
      <p><a href="#/plans">Back to Plans</a></p>
      <Card title="Plan summary">
        <dl>
          <dt>Crop</dt><dd>{detail.cropCode}</dd>
          <dt>Status</dt><dd>{detail.status}</dd>
          <dt>Area</dt><dd>{detail.areaHa} ha (margin {detail.areaMarginHa} ha)</dd>
          <dt>Planting date</dt><dd>{detail.plantingDate}</dd>
          <dt>Harvest period</dt><dd>{detail.harvestPeriod}</dd>
          <dt>Revision</dt><dd>{detail.revisionNumber}</dd>
        </dl>
      </Card>
      <p className="hint">Only fields the server authorizes are shown. Individual records require server authorization.</p>
      <DataTable
        caption="Plan revision on record"
        columns={["Field", "Value"]}
        rows={[
          ["Crop", detail.cropCode],
          ["Status", detail.status],
          ["Area", `${detail.areaHa} ha`],
          ["Harvest period", detail.harvestPeriod],
        ]}
      />
    </section>
  );
}
