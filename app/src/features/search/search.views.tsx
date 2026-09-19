import { useEffect, useState } from "react";
import { Alert } from "../../components/Alert";
import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { Skeleton } from "../../components/Skeleton";
import { TextField } from "../../components/TextField";
import { fetchAggregates, fetchReferences, isServerError } from "../../lib/api";
import { CROPS, ORG_ID } from "../../lib/store";
import type { AggregateRow, Plan, ReferenceRecord, Role } from "../../types";

interface SearchHit {
  key: string;
  kind: string;
  title: string;
  subtitle: string;
  href: string;
}

function planHits(plans: Plan[], query: string): SearchHit[] {
  // The caller passes only plans already visible to the signed-in role.
  // Plan detail itself remains server-authorized per record.
  return plans
    .filter((plan) => `${plan.crop} ${plan.harvestPeriod} ${plan.farm} ${plan.state}`.toLowerCase().includes(query))
    .map((plan) => ({
      key: `plan-${plan.id}`,
      kind: "Plan",
      title: `${plan.crop} plan ${plan.id}`,
      subtitle: `${plan.harvestPeriod} · ${plan.farm} · ${plan.state}`,
      href: `#/result/${plan.id}`,
    }));
}

function aggregateHits(rows: AggregateRow[], query: string): SearchHit[] {
  return rows
    .filter((row) => `${row.cropCode} ${row.harvestPeriod}`.toLowerCase().includes(query))
    .map((row) => ({
      key: `agg-${row.cropCode}-${row.harvestPeriod}`,
      kind: "Aggregate",
      title: `${row.cropCode} ${row.harvestPeriod}`,
      subtitle: `${row.farmers} farmers · ${row.plannedAreaHa} ha`,
      href: `#/crop/${row.cropCode}`,
    }));
}

function referenceHits(references: ReferenceRecord[], query: string): SearchHit[] {
  return references
    .filter((reference) => `${reference.crop} ${reference.geography} ${reference.period} ${reference.source}`.toLowerCase().includes(query))
    .map((reference) => ({
      key: `ref-${reference.id}`,
      kind: "Reference",
      title: `${reference.crop} reference ${reference.version}`,
      subtitle: `${reference.geography} · ${reference.period} · ${reference.workflow}`,
      href: `#/ref/${reference.id}`,
    }));
}

function cropHits(query: string): SearchHit[] {
  return CROPS
    .filter((crop) => `${crop.code} ${crop.name}`.toLowerCase().includes(query))
    .map((crop) => ({
      key: `crop-${crop.code}`,
      kind: "Crop",
      title: crop.name,
      subtitle: crop.supported ? "Supported for planning" : "Not yet supported for planning",
      href: `#/crop/${crop.code}`,
    }));
}

export function GlobalSearch({ plans, role }: { plans: Plan[]; role: Role }) {
  const [query, setQuery] = useState("");
  const [aggregates, setAggregates] = useState<AggregateRow[]>([]);
  const [references, setReferences] = useState<ReferenceRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([fetchAggregates(ORG_ID), fetchReferences(ORG_ID)]).then(([rows, refs]) => {
      if (!active) return;
      setAggregates(rows);
      setReferences(refs);
      setLoaded(true);
      setError(null);
    }).catch((reason: unknown) => {
      if (!active) return;
      setError(isServerError(reason) ? reason.message : "Search indexes are unavailable.");
      setLoaded(true);
    });
    return () => { active = false; };
  }, []);

  const needle = query.trim().toLowerCase();
  const hits = needle === "" ? [] : [
    ...planHits(plans, needle),
    ...aggregateHits(aggregates, needle),
    ...referenceHits(references, needle),
    ...cropHits(needle),
  ];

  return (
    <section aria-labelledby="search-h">
      <h2 id="search-h">Search</h2>
      <p className="hint">Search respects your role. Live full-text search needs API-M2-006; this screen searches loaded plans, aggregates, references, and crops.</p>
      {role === "farmer" && <p className="hint">Farmers search their own plans plus shared crops and references.</p>}
      {error && <Alert tone="error" title="Search indexes unavailable">{error}</Alert>}
      <TextField name="global-search" label="Search crops, plans, aggregates, references" value={query}
        onChange={(event) => setQuery(event.target.value)} placeholder="e.g. Tomato" />
      {!loaded && <Skeleton label="Loading search indexes" />}
      {loaded && needle !== "" && hits.length === 0 && (
        <EmptyState title="No matches" body="Nothing visible to your role matches this search." />
      )}
      {hits.length > 0 && (
        <ul className="cards">
          {hits.map((hit) => (
            <li key={hit.key}>
              <article className="card" aria-label={`${hit.kind}: ${hit.title}`}>
                <h3>{hit.title}</h3>
                <p className="hint">{hit.kind} · {hit.subtitle}</p>
                <p><a href={hit.href}>Open {hit.kind.toLowerCase()}</a></p>
              </article>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function SearchCard() {
  return (
    <Card title="Search">
      <p>Find crops, plans, aggregates, and references.</p>
      <p><a href="#/search">Open search</a></p>
    </Card>
  );
}
