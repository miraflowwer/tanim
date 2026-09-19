// Crop explorer (§07): search/filter, support status, yield availability,
// organization aggregate where permitted, price/climate/suitability context.
// Unsupported crops stay visible with the reason — never hidden. Alternative
// inspection is worded "Another crop to inspect" and never ranked "best".
import { useEffect, useMemo, useState } from "react";
import { Alert } from "../../components/Alert";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { Skeleton } from "../../components/Skeleton";
import { TextField } from "../../components/TextField";
import { Breadcrumbs, PageHeader } from "../../components/layout/Shell";
import { fetchCropYield, fetchCrops, isServerError } from "../../lib/api";
import { ORG_SCOPE } from "../../lib/copy";
import { CROPS, ORG_ID } from "../../lib/store";
import type { CropDetail } from "../../types";

export function CropExplorer() {
  const [server, setServer] = useState<CropDetail[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [supportedOnly, setSupportedOnly] = useState(false);
  useEffect(() => {
    let active = true;
    fetchCrops().then((rows) => {
      if (active) { setServer(rows); setError(null); }
    }).catch((reason: unknown) => {
      if (active) setError(isServerError(reason) ? reason.message : "The crop service is unavailable. Showing the local crop list.");
    });
    return () => { active = false; };
  }, []);
  const rows = useMemo(() => {
    const base: CropDetail[] = (server ?? CROPS.map((c) => ({
      code: c.code, name: c.name, supported: c.supported,
      yieldMtPerHa: null, yieldGeography: null,
      priceNote: "Market price is context only.",
      climateNote: "Climate is context only.",
      suitabilityNote: "Suitability is contextual information, not an automatic planting recommendation.",
    })));
    return base
      .filter((c) => c.name.toLowerCase().includes(query.trim().toLowerCase()))
      .filter((c) => (supportedOnly ? c.supported : true));
  }, [server, query, supportedOnly]);
  return (
    <section aria-labelledby="crops-h">
      <PageHeader title="Crop explorer" purpose="Supported crops can be planned. Unsupported crops explain what coverage is missing." />
      <h2 id="crops-h" className="visually-hidden">Crop explorer</h2>
      <form role="search" onSubmit={(e) => e.preventDefault()}>
        <TextField name="crop-search" label="Search crops" value={query} onChange={(e) => setQuery(e.target.value)} />
      </form>
      <p className="row">
        <Button variant={supportedOnly ? "primary" : "secondary"} onClick={() => setSupportedOnly((v) => !v)}>
          {supportedOnly ? "Showing: supported only" : "Filter: supported only"}
        </Button>
      </p>
      {error && <Alert title="Crop service notice">{error}</Alert>}
      {rows.length === 0 && <EmptyState title="No crops match." actionLabel="Clear search" onAction={() => { setQuery(""); setSupportedOnly(false); }} />}
      <ul className="cards">
        {rows.map((crop) => (
          <li key={crop.code}>
            <Card title={crop.name}>
              <p>{crop.supported ? "Supported for planning" : "Not yet supported — no safe production and area match"}</p>
              <p><a href={`#/crops/${crop.code}`}>Inspect {crop.name}</a></p>
            </Card>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function CropDetailView({ cropCode }: { cropCode: string }) {
  const entry = CROPS.find((c) => c.code === cropCode);
  const [yieldMt, setYieldMt] = useState<number | null | undefined>(undefined);
  useEffect(() => {
    let active = true;
    fetchCropYield(cropCode, ORG_SCOPE).then((value) => {
      if (active) setYieldMt(value);
    }).catch(() => { if (active) setYieldMt(null); });
    return () => { active = false; };
  }, [cropCode]);
  if (!entry) {
    return (
      <section aria-labelledby="crop-h">
        <h2 id="crop-h">Crop</h2>
        <Alert tone="error" title="Crop not found">TANIM has no record for this crop code.</Alert>
        <p><a href="#/crops">Back to crops</a></p>
      </section>
    );
  }
  return (
    <section aria-labelledby="crop-h">
      <Breadcrumbs trail={[{ label: "Crops", href: "#/crops" }, { label: entry.name }]} />
      <PageHeader title={entry.name} purpose={entry.supported ? "Supported for planning." : "Not yet supported."} />
      <h2 id="crop-h" className="visually-hidden">{entry.name}</h2>
      <Card title="Yield reference availability">
        {yieldMt === undefined && <Skeleton label="Checking yield coverage…" />}
        {yieldMt !== undefined && yieldMt === null && (
          <p>TANIM cannot estimate production for this crop and region yet.</p>
        )}
        {yieldMt !== undefined && yieldMt !== null && (
          <p>Reference yield {yieldMt} MT/ha for {ORG_SCOPE} ({ORG_ID}).</p>
        )}
      </Card>
      <Card title="Price context">
        <p>Market price context. This is not the reviewed comparison reference used for the coordination result.</p>
      </Card>
      <Card title="Climate and suitability">
        <p>Suitability is contextual information, not an automatic planting recommendation.</p>
      </Card>
      <Card title="Another crop to inspect">
        <p className="hint">TANIM does not rank a best crop. Compare inspected crops side by side.</p>
        <p className="row">
          {CROPS.filter((c) => c.code !== cropCode).slice(0, 3).map((c) => (
            <Button key={c.code} variant="secondary" onClick={() => (location.hash = `#/crops/${c.code}`)}>
              Inspect {c.name}
            </Button>
          ))}
        </p>
      </Card>
      <p className="hint"><a href="#/crops">Back to crops</a></p>
    </section>
  );
}
