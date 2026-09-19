// Organization onboarding (§06): join/create, invitation accept/decline,
// explicit operational consent + optional research consent, first farm.
// Role-aware completion: Farmer -> #/home. Exact GPS never required.
import { useState } from "react";
import { Alert } from "../../components/Alert";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { TextField } from "../../components/TextField";
import { NumberField } from "../../components/NumberField";
import { PageHeader } from "../../components/layout/Shell";
import { createFarmFull, grantConsent, isServerError } from "../../lib/api";
import { ORG_ID } from "../../lib/store";
import type { InviteDetail } from "../../types";

export function OnboardingOrganization() {
  const [mode, setMode] = useState<"join" | "create">("join");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (mode === "join" && !code.trim()) {
      setError("Enter your invitation code.");
      return;
    }
    if (mode === "create" && !name.trim()) {
      setError("Enter an organization name.");
      return;
    }
    setError(null);
    location.hash = mode === "join" ? `#/invite/${encodeURIComponent(code.trim())}` : "#/onboarding/consent";
  }
  return (
    <section aria-labelledby="org-h">
      <PageHeader title="Join your organization" purpose="Step 1 of 3. Farmers join with the Farmer role unless an approved invitation says otherwise." />
      <h2 id="org-h" className="visually-hidden">Join your organization</h2>
      <p className="row" role="group" aria-label="Organization path">
        <Button variant={mode === "join" ? "primary" : "secondary"} onClick={() => setMode("join")}>Join with code</Button>
        <Button variant={mode === "create" ? "primary" : "secondary"} onClick={() => setMode("create")}>Create organization</Button>
      </p>
      <form onSubmit={submit} noValidate>
        {mode === "join"
          ? <TextField name="code" label="Invitation code" autoComplete="off" value={code} onChange={(e) => setCode(e.target.value)} />
          : <TextField name="org" label="Organization name" autoComplete="organization" value={name} onChange={(e) => setName(e.target.value)} />}
        {error && <p role="alert" className="err">{error}</p>}
        <Button type="submit">Continue</Button>
      </form>
    </section>
  );
}

export function InviteAccept({ token }: { token: string }) {
  // Invitation detail is contract-ready (API-004). Until the backend serves
  // invites, resolve state locally without granting any role client-side.
  const [state, setState] = useState<InviteDetail["state"]>("valid");
  const [done, setDone] = useState<string | null>(null);
  if (done) {
    return (
      <section aria-labelledby="inv-h">
        <h2 id="inv-h">Invitation {done}</h2>
        <Alert title={done === "accepted" ? "Welcome" : "Recorded"}>
          {done === "accepted"
            ? "Your invitation was accepted. Continue to consent to finish setup."
            : "Your invitation was declined. No role was granted."}
        </Alert>
        {done === "accepted" && <p><a href="#/onboarding/consent">Continue to consent</a></p>}
      </section>
    );
  }
  return (
    <section aria-labelledby="inv-h">
      <PageHeader title="Organization invitation" purpose="Review the invitation before you accept. Accept and decline are separated to prevent accidental taps." />
      <h2 id="inv-h" className="visually-hidden">Organization invitation</h2>
      <Card title="Invitation">
        <dl>
          <dt>Organization</dt><dd>Coop Demo Org</dd>
          <dt>Invited role</dt><dd>Farmer</dd>
          <dt>Code</dt><dd>{token || "missing"}</dd>
          <dt>Status</dt><dd>{state}</dd>
        </dl>
        {(!token) && <Alert tone="error" title="Invalid invitation">This invitation link is incomplete.</Alert>}
      </Card>
      <p className="row">
        <Button onClick={() => (state === "valid" ? setDone("accepted") : setState("valid"))}>Accept invitation</Button>
      </p>
      <p className="row">
        <Button variant="secondary" onClick={() => setDone("declined")}>Decline</Button>
      </p>
      <p className="hint">Expired, revoked, and already-used invitations stay visible with their state instead of disappearing.</p>
    </section>
  );
}

const OPERATIONAL_PURPOSE = "Operate your planting plans and coordination results.";
const RESEARCH_PURPOSE = "Optional research use of anonymized coordination data.";

export function OnboardingConsent() {
  const [operational, setOperational] = useState(false);
  const [research, setResearch] = useState(false); // unchecked by default
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!operational) {
      setNote("Operational consent is required for TANIM coordination. Research consent stays optional.");
      return;
    }
    setBusy(true);
    setNote(null);
    try {
      await grantConsent(ORG_ID, "operational", OPERATIONAL_PURPOSE, "v1");
      if (research) await grantConsent(ORG_ID, "research", RESEARCH_PURPOSE, "v1");
      location.hash = "#/onboarding/farm";
    } catch (reason: unknown) {
      setNote(isServerError(reason) ? reason.message : "Consent could not be saved. Your choices have been kept.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-labelledby="consent-h">
      <PageHeader title="Consent" purpose="Step 2 of 3. Operational and research consent are separate. Declining research never blocks TANIM." />
      <h2 id="consent-h" className="visually-hidden">Consent</h2>
      <form onSubmit={submit}>
        <Card title="Operational consent (required)">
          <p>{OPERATIONAL_PURPOSE}</p>
          <p className="hint">Policy v1. Required for coordination service.</p>
          <label className="check">
            <input type="checkbox" checked={operational} onChange={(e) => setOperational(e.target.checked)} />
            I agree to operational use
          </label>
        </Card>
        <Card title="Research consent (optional)">
          <p>{RESEARCH_PURPOSE}</p>
          <p className="hint">Unchecked by default. You can withdraw later under Privacy &amp; Consent.</p>
          <label className="check">
            <input type="checkbox" checked={research} onChange={(e) => setResearch(e.target.checked)} />
            I agree to optional research use
          </label>
        </Card>
        {note && <p role="status">{note}</p>}
        <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Continue"}</Button>
      </form>
    </section>
  );
}

export function OnboardingFarm() {
  const [name, setName] = useState("");
  const [municipality, setMunicipality] = useState("");
  const [region, setRegion] = useState("CALABARZON");
  const [area, setArea] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !municipality.trim()) {
      setNote("Enter a farm name and municipality. Map and GPS are never required.");
      return;
    }
    setBusy(true);
    setNote(null);
    try {
      await createFarmFull(ORG_ID, {
        name: name.trim(),
        municipality: municipality.trim(),
        region: region.trim(),
        totalAreaHa: area ? Number(area) : null,
      });
      location.hash = "#/home";
    } catch (reason: unknown) {
      setNote(isServerError(reason) ? reason.message : "The farm service is unavailable. Your entries have been kept.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-labelledby="farm-h">
      <PageHeader title="Set up your farm" purpose="Step 3 of 3. A name and municipality are enough — coordinates stay optional." />
      <h2 id="farm-h" className="visually-hidden">Set up your farm</h2>
      <form onSubmit={submit} noValidate>
        <TextField name="farm-name" label="Farm or location name" value={name} onChange={(e) => setName(e.target.value)} />
        <TextField name="municipality" label="Municipality" value={municipality} onChange={(e) => setMunicipality(e.target.value)} />
        <TextField name="region" label="Region" value={region} onChange={(e) => setRegion(e.target.value)} />
        <NumberField name="area" label="Total area in hectares (ha, optional)" min={0} step={0.1}
          value={area} onChange={(e) => setArea(e.target.value)} />
        {note && <p role="status">{note}</p>}
        <Button type="submit" disabled={busy}>{busy ? "Saving…" : "Finish setup"}</Button>
      </form>
      <p className="hint"><a href="#/home">Skip for now</a></p>
    </section>
  );
}
