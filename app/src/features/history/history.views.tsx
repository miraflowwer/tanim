import { useEffect, useState } from "react";
import { Alert } from "../../components/Alert";
import { Card } from "../../components/Card";
import { DataTable } from "../../components/DataTable";
import { EmptyState } from "../../components/EmptyState";
import { Skeleton } from "../../components/Skeleton";
import { fetchCalculation, fetchRevisions, isServerError, type CalculationEntry, type RevisionEntry } from "./history.api";

export function CalculationHistory({ planId, calculationId }: { planId: string; calculationId?: string }) {
  const [revisions, setRevisions] = useState<RevisionEntry[] | null>(null);
  const [calculation, setCalculation] = useState<CalculationEntry | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchRevisions(planId).then((rows) => {
      if (!active) return;
      setRevisions(rows);
      setError(null);
    }).catch((reason: unknown) => {
      if (active) setError(isServerError(reason) ? reason.message : "Calculation history is unavailable.");
    });
    if (calculationId) {
      fetchCalculation(calculationId).then((result) => {
        if (active) setCalculation(result);
      }).catch(() => {
        if (active) setError("The stored calculation is unavailable.");
      });
    }
    return () => { active = false; };
  }, [planId, calculationId]);

  if (error && revisions === null) return <Alert tone="error" title="History unavailable">{error}</Alert>;
  if (revisions === null) return <Skeleton label="Loading calculation history" />;
  return (
    <section aria-labelledby="history-h">
      <h2 id="history-h">Calculation history</h2>
      {error && <Alert tone="error" title="Stored calculation unavailable">{error}</Alert>}
      {calculation && (
        <Card title={`Calculation ${calculation.calculationId}`}>
          <dl>
            <dt>Status</dt><dd>{calculation.status}</dd>
            <dt>Expected production</dt><dd>{calculation.expectedProduction} MT</dd>
            <dt>Engine version</dt><dd>{calculation.engineVersion}</dd>
            <dt>Policy version</dt><dd>{calculation.policyVersion}</dd>
            <dt>Yield reference</dt><dd>{calculation.yieldReference}</dd>
            <dt>Comparison reference</dt><dd>{calculation.comparisonReference}</dd>
          </dl>
          <p className="hint">Stored provenance never changes when newer references arrive.</p>
        </Card>
      )}
      {revisions.length === 0 ? (
        <EmptyState title="No revisions" body="Adjustments to this plan will appear here." />
      ) : (
        <DataTable
          caption="Plan revisions in order recorded"
          columns={["Revision", "Area", "Margin", "Planting", "Harvest", "Recorded"]}
          rows={revisions.map((revision) => [
            String(revision.revisionNumber),
            `${revision.areaHa} ha`,
            `${revision.areaMarginHa} ha`,
            revision.plantingDate,
            revision.harvestPeriod,
            revision.createdAt || "—",
          ])}
        />
      )}
    </section>
  );
}
