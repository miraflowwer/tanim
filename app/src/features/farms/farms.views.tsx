// Farmer farms (§07): list/create/detail. Only the signed-in farmer's own
// farms are visible — the list endpoint already scopes by role.
import { useEffect, useState } from "react";
import { Alert } from "../../components/Alert";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { Skeleton } from "../../components/Skeleton";
import { NumberField } from "../../components/NumberField";
import { TextField } from "../../components/TextField";
import { Breadcrumbs, PageHeader } from "../../components/layout/Shell";
import { createFarmFull, fetchFarm, fetchFarms, isServerError, updateFarm } from "../../lib/api";
import { ORG_ID } from "../../lib/store";
import type { Farm } from "../../types";

function FarmCard({ farm }: { farm: Farm }) {
  return (
    <Card title={farm.name}>
      <p>{[farm.municipality, farm.region].filter(Boolean).join(" · ") || "Location not set"}</p>
      {farm.totalAreaHa !== null && <p className="hint">{farm.totalAreaHa} ha total</p>}
      <p><a href={`#/farms/${farm.id}`}>View farm</a></p>
    </Card>
  );
}

export function FarmsList() {
  const [farms, setFarms] = useState<Farm[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    fetchFarms(ORG_ID).then((rows) => {
      if (active) setFarms(rows);
    }).catch((reason: unknown) => {
      if (active) setError(isServerError(reason) ? reason.message : "The farm service is unavailable.");
    });
    return () => { active = false; };
  }, []);
  return (
    <section aria-labelledby="farms-h">
      <PageHeader title="My farms" purpose="Only your own farms are listed here."
        action={<Button onClick={() => (location.hash = "#/farms/new")}>Add farm</Button>} />
      <h2 id="farms-h" className="visually-hidden">My farms</h2>
      {farms === null && !error && <Skeleton label="Loading farms…" />}
      {error && <Alert tone="error" title="Farms unavailable">{error}</Alert>}
      {farms !== null && farms.length === 0 && (
        <EmptyState title="No farms yet." actionLabel="Add farm" onAction={() => (location.hash = "#/farms/new")} />
      )}
      {farms !== null && farms.length > 0 && (
        <ul className="cards">{farms.map((farm) => <li key={farm.id}><FarmCard farm={farm} /></li>)}</ul>
      )}
    </section>
  );
}

export function FarmNew() {
  const [name, setName] = useState("");
  const [municipality, setMunicipality] = useState("");
  const [region, setRegion] = useState("CALABARZON");
  const [area, setArea] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !municipality.trim()) {
      setError("Enter a farm name and municipality. Coordinates are never required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const farm = await createFarmFull(ORG_ID, {
        name: name.trim(), municipality: municipality.trim(), region: region.trim(),
        totalAreaHa: area ? Number(area) : null,
      });
      location.hash = `#/farms/${farm.id}`;
    } catch (reason: unknown) {
      setError(isServerError(reason) ? reason.message : "The farm service is unavailable. Your entries have been kept.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-labelledby="farm-new-h">
      <Breadcrumbs trail={[{ label: "Farms", href: "#/farms" }, { label: "New farm" }]} />
      <PageHeader title="Add farm" purpose="A name and municipality are enough." />
      <h2 id="farm-new-h" className="visually-hidden">Add farm</h2>
      <form onSubmit={submit} noValidate>
        <TextField name="farm-name" label="Farm or location name" value={name} onChange={(e) => setName(e.target.value)} />
        <TextField name="municipality" label="Municipality" value={municipality} onChange={(e) => setMunicipality(e.target.value)} />
        <TextField name="region" label="Region" value={region} onChange={(e) => setRegion(e.target.value)} />
        <NumberField name="area" label="Total area in hectares (ha, optional)" min={0} step={0.1}
          value={area} onChange={(e) => setArea(e.target.value)} />
        {error && <p role="alert" className="err">{error}</p>}
        <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save farm"}</Button>
      </form>
    </section>
  );
}

export function FarmDetail({ farmId }: { farmId: string }) {
  const [farm, setFarm] = useState<Farm | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [municipality, setMunicipality] = useState("");
  const [region, setRegion] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    fetchFarm(farmId).then((row) => {
      if (!active) return;
      setFarm(row);
      setName(row.name);
      setMunicipality(row.municipality ?? "");
      setRegion(row.region ?? "");
    }).catch((reason: unknown) => {
      if (active) setError(isServerError(reason) ? reason.message : "The farm service is unavailable.");
    });
    return () => { active = false; };
  }, [farmId]);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!farm) return;
    try {
      const updated = await updateFarm(farm.id, farm.organizationId, {
        name: name.trim(), municipality: municipality.trim(), region: region.trim(),
        totalAreaHa: farm.totalAreaHa,
      });
      setFarm(updated);
      setEditing(false);
      setNotice("Farm saved.");
    } catch (reason: unknown) {
      setNotice(isServerError(reason) ? reason.message : "The farm service is unavailable. Your entries have been kept.");
    }
  }
  if (error) {
    return (
      <section aria-labelledby="farm-d-h">
        <h2 id="farm-d-h">Farm</h2>
        <Alert tone="error" title="Farm unavailable">{error}</Alert>
        <p><a href="#/farms">Back to farms</a></p>
      </section>
    );
  }
  if (!farm) return <section aria-label="Loading farm"><Skeleton label="Loading farm…" /></section>;
  return (
    <section aria-labelledby="farm-d-h">
      <Breadcrumbs trail={[{ label: "Farms", href: "#/farms" }, { label: farm.name }]} />
      <PageHeader title={farm.name} purpose={[farm.municipality, farm.region].filter(Boolean).join(" · ")}
        action={<Button variant="secondary" onClick={() => setEditing((v) => !v)}>{editing ? "Cancel" : "Edit farm"}</Button>} />
      <h2 id="farm-d-h" className="visually-hidden">{farm.name}</h2>
      {!editing && (
        <Card title="Farm record">
          <dl>
            <dt>Municipality</dt><dd>{farm.municipality ?? "Not set"}</dd>
            <dt>Region</dt><dd>{farm.region ?? "Not set"}</dd>
            <dt>Total area</dt><dd>{farm.totalAreaHa !== null ? `${farm.totalAreaHa} ha` : "Not set"}</dd>
          </dl>
        </Card>
      )}
      {editing && (
        <form onSubmit={save} noValidate>
          <TextField name="farm-name" label="Farm or location name" value={name} onChange={(e) => setName(e.target.value)} />
          <TextField name="municipality" label="Municipality" value={municipality} onChange={(e) => setMunicipality(e.target.value)} />
          <TextField name="region" label="Region" value={region} onChange={(e) => setRegion(e.target.value)} />
          <Button type="submit">Save changes</Button>
        </form>
      )}
      {notice && <p role="status">{notice}</p>}
    </section>
  );
}
