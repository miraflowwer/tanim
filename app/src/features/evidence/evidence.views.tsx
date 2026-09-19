import { useEffect, useState } from "react";
import { Alert } from "../../components/Alert";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { DataTable } from "../../components/DataTable";
import { EmptyState } from "../../components/EmptyState";
import { NumberField } from "../../components/NumberField";
import { Select } from "../../components/Select";
import { Skeleton } from "../../components/Skeleton";
import { Status } from "../../components/Status";
import { TextField } from "../../components/TextField";
import { fetchReferences } from "../../lib/api";
import { ORG_ID } from "../../lib/store";
import type { ReferenceRecord, ReferenceType, Role } from "../../types";
import {
  correctCandidate,
  createCandidate,
  fetchReferenceDetail,
  flagReference,
  isServerError,
  supersedeReference,
  transitionWithNote,
} from "./evidence.api";
import type { CandidateInput, ReferenceDetailModel } from "./evidence.types";

const QUEUE_VIEWS = ["Under review", "Needs correction", "Recently verified", "Rejected", "Expiring and stale"] as const;

function queueOf(reference: ReferenceRecord): string {
  if (reference.workflow === "under_review") return "Under review";
  if (reference.workflow === "rejected") return "Rejected";
  if (reference.workflow === "verified") return "Recently verified";
  if (reference.verificationStatus === "stale") return "Expiring and stale";
  return "Needs correction";
}

export function ReviewQueue({ role }: { role: Role }) {
  const [refs, setRefs] = useState<ReferenceRecord[] | null>(null);
  const [view, setView] = useState<string>("Under review");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchReferences(ORG_ID).then((records) => {
      if (!active) return;
      setRefs(records);
      setError(null);
    }).catch((reason: unknown) => {
      if (active) setError(isServerError(reason) ? reason.message : "The review queue is unavailable.");
    });
    return () => { active = false; };
  }, []);

  if (error) return <Alert tone="error" title="Review queue unavailable">{error}</Alert>;
  if (refs === null) return <Skeleton label="Loading review queue" />;
  const shown = refs.filter((reference) => queueOf(reference) === view);
  return (
    <section aria-labelledby="review-h">
      <h2 id="review-h">Review queue</h2>
      <p className="hint">Verification is enforced by FastAPI. Synthetic demo evidence cannot be verified for production.</p>
      <p><a href="#/refnew">Submit candidate reference</a></p>
      <div className="filters" role="search" aria-label="Filter review queue">
        <Select name="q-view" label="Queue view" options={[...QUEUE_VIEWS]} value={view}
          onChange={(event) => setView(event.target.value)} />
      </div>
      {shown.length === 0 ? (
        <EmptyState title={`No references ${view.toLowerCase()}`} body="New candidates appear here after submission." />
      ) : (
        <ul className="cards">
          {shown.map((reference) => (
            <li key={reference.id}>
              <article className="card" aria-label={`${reference.crop} reference ${reference.version}`}>
                <h3>{reference.crop} · {reference.amountMt} {reference.unit}</h3>
                <Status label={reference.workflow} tone={reference.workflow === "verified" ? "ok" : reference.workflow === "rejected" ? "bad" : "warn"} />
                {reference.synthetic && <p role="note" className="badge">Synthetic demo evidence. Verification is blocked.</p>}
                <p className="hint">{reference.geography} · {reference.period} · {reference.source}</p>
                <p>
                  <a href={`#/ref/${reference.id}`}>Open reference detail</a>
                  {role !== "reviewer" && !reference.synthetic && <span className="hint"> Review actions need a reviewer role.</span>}
                </p>
              </article>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

type DetailTab = "Details" | "Review history" | "Versions";

export function ReferenceDetail({ refId, role }: { refId: string; role: Role }) {
  const [detail, setDetail] = useState<ReferenceDetailModel | null>(null);
  const [tab, setTab] = useState<DetailTab>("Details");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [correction, setCorrection] = useState<"correct" | "supersede" | null>(null);

  useEffect(() => {
    let active = true;
    setDetail(null);
    fetchReferenceDetail(refId).then((result) => {
      if (!active) return;
      setDetail(result);
      setError(null);
    }).catch(() => {
      if (active) setError("This reference is unavailable. It may not exist or you may lack access.");
    });
    return () => { active = false; };
  }, [refId]);

  async function act(action: "submit" | "verify" | "reject" | "reopen" | "expire") {
    if (!detail || busy) return;
    if (action === "reject" && note.trim() === "") {
      setError("Rejection needs a note explaining why.");
      return;
    }
    setBusy(true);
    try {
      const updated = await transitionWithNote(detail.id, action, note);
      setDetail(updated);
      setNote("");
      setError(null);
    } catch (reason: unknown) {
      setError(isServerError(reason) ? reason.message : "The review action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function flag() {
    if (!detail || busy || note.trim() === "") {
      setError("Write a flag note first.");
      return;
    }
    setBusy(true);
    try {
      await flagReference(detail.id, note);
      const updated = await fetchReferenceDetail(detail.id);
      setDetail(updated);
      setNote("");
      setError(null);
    } catch (reason: unknown) {
      setError(isServerError(reason) ? reason.message : "Flagging failed.");
    } finally {
      setBusy(false);
    }
  }

  if (error && detail === null) return <Alert tone="error" title="Reference unavailable">{error}</Alert>;
  if (detail === null) return <Skeleton label="Loading reference detail" />;
  const canReview = role === "reviewer" && !detail.synthetic;
  return (
    <section aria-labelledby="refd-h">
      <h2 id="refd-h">{detail.crop} reference</h2>
      <p><a href="#/review">Back to Review queue</a></p>
      {detail.synthetic && <p role="note" className="badge">Synthetic demo evidence. Verification is blocked.</p>}
      {error && <Alert tone="error" title="Review action failed">{error}</Alert>}
      <div className="row" role="tablist" aria-label="Reference sections">
        {(["Details", "Review history", "Versions"] as DetailTab[]).map((name) => (
          <Button key={name} variant="secondary" role="tab" aria-selected={tab === name} onClick={() => setTab(name)}>
            {name}
          </Button>
        ))}
      </div>
      {tab === "Details" && (
        <Card title="Reference details">
          <dl>
            <dt>Amount</dt><dd>{detail.amountMt} MT</dd>
            <dt>Geography</dt><dd>{detail.geography}</dd>
            <dt>Period</dt><dd>{detail.period}</dd>
            <dt>Source</dt><dd>{detail.source}</dd>
            <dt>Evidence note</dt><dd>{detail.evidenceNote || "No note recorded."}</dd>
            <dt>Reviewer</dt><dd>{detail.reviewer}</dd>
            <dt>Review state</dt><dd>{detail.workflow}</dd>
            <dt>Verification</dt><dd>{detail.verificationStatus}</dd>
            <dt>Version</dt><dd>{detail.version}</dd>
            <dt>Effective</dt><dd>{detail.effectiveFrom} to {detail.effectiveTo}</dd>
            <dt>Verified at</dt><dd>{detail.verifiedAt || "Not verified"}</dd>
          </dl>
        </Card>
      )}
      {tab === "Review history" && (
        <Card title="Review history">
          {detail.history.length === 0 && <p>No review events recorded yet.</p>}
          {detail.history.length > 0 && (
            <DataTable
              caption="Review events in order recorded"
              columns={["Action", "Actor", "At", "Note"]}
              rows={detail.history.map((entry) => [entry.action, entry.actor, entry.at, entry.note || "—"])}
            />
          )}
          {detail.flags.length > 0 && (
            <DataTable
              caption="Flags raised on this reference"
              columns={["By", "At", "Note"]}
              rows={detail.flags.map((flag) => [flag.by, flag.at, flag.note || "—"])}
            />
          )}
        </Card>
      )}
      {tab === "Versions" && (
        <Card title="Version lineage">
          <dl>
            <dt>Current version</dt><dd>{detail.version}</dd>
            <dt>Predecessor</dt>
            <dd>{detail.predecessorId ? <a href={`#/ref/${detail.predecessorId}`}>{detail.predecessorId}</a> : "None"}</dd>
            <dt>Successor</dt>
            <dd>{detail.successorId ? <a href={`#/ref/${detail.successorId}`}>{detail.successorId}</a> : "None"}</dd>
          </dl>
          <p className="hint">A supersede links the old verified version to its draft successor. Versions never change in place.</p>
        </Card>
      )}
      <Card title="Review actions">
        <p className="hint">The server decides whether a transition is legal. Rejection needs a note.</p>
        <TextField name="review-note" label="Reviewer note" value={note}
          onChange={(event) => setNote(event.target.value)} placeholder="Reason for this action" />
        <p className="row">
          <Button variant="secondary" disabled={busy || !canReview} onClick={() => void act("submit")}>Submit for review</Button>
          <Button variant="secondary" disabled={busy || !canReview} onClick={() => void act("verify")}>Mark verified</Button>
          <Button variant="secondary" disabled={busy || !canReview} onClick={() => void act("reject")}>Reject</Button>
          <Button variant="secondary" disabled={busy || !canReview} onClick={() => void act("reopen")}>Reopen draft</Button>
          <Button variant="secondary" disabled={busy || !canReview} onClick={() => void act("expire")}>Mark expired</Button>
          <Button variant="secondary" disabled={busy} onClick={() => void flag()}>Flag</Button>
        </p>
        {!canReview && <p className="hint">Only reviewers can change review state. Synthetic demo evidence stays read-only.</p>}
      </Card>
      {canReview && (
        <Card title="Correction and succession">
          <p className="hint">Corrections keep organization, crop, geography, and period. A supersede links the old verified version to its draft successor.</p>
          <p className="row">
            <Button variant="secondary" onClick={() => setCorrection(correction === "correct" ? null : "correct")}>
              Correct draft
            </Button>
            <Button variant="secondary" onClick={() => setCorrection(correction === "supersede" ? null : "supersede")}>
              Supersede
            </Button>
          </p>
          {correction && <CandidateForm mode={correction} refId={detail.id} />}
        </Card>
      )}
    </section>
  );
}

const REFERENCE_TYPE_OPTIONS: ReferenceType[] = [
  "local_committed_demand",
  "local_historical_absorption",
  "national_utilization_context",
  "historical_production_baseline",
  "demo_coordination_baseline",
];

const EMPTY_CANDIDATE: CandidateInput = {
  cropCode: "tomato",
  amountMt: 0,
  referenceType: "local_committed_demand",
  geography: "CALABARZON",
  period: "2026-Q4",
  source: "",
  evidenceNote: "",
  effectiveFrom: "",
  effectiveTo: "",
};

export function CandidateForm({ mode, refId }: { mode: "new" | "correct" | "supersede"; refId?: string }) {
  const [form, setForm] = useState<CandidateInput>(EMPTY_CANDIDATE);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  function set<K extends keyof CandidateInput>(key: K, value: CandidateInput[K]) {
    setForm((previous) => ({ ...previous, [key]: value }));
  }

  async function submit() {
    if (!(form.amountMt > 0)) {
      setFormError("Amount must be greater than zero.");
      return;
    }
    if (form.source.trim() === "") {
      setFormError("Source is required.");
      return;
    }
    setFormError(null);
    setBusy(true);
    try {
      const payload = { ...form, organizationId: ORG_ID };
      const saved = mode === "new"
        ? await createCandidate(payload)
        : mode === "correct" && refId
          ? await correctCandidate(refId, payload)
          : mode === "supersede" && refId
            ? await supersedeReference(refId, payload)
            : null;
      if (!saved) throw new Error("missing reference");
      setSavedId(saved.id);
      setError(null);
    } catch (reason: unknown) {
      setError(isServerError(reason) ? reason.message : "Saving the candidate failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="cand-h">
      <h2 id="cand-h">
        {mode === "new" ? "Submit candidate reference" : mode === "correct" ? "Correct draft reference" : "Supersede with successor"}
      </h2>
      <p className="hint">New candidates start unverified. There is no control here that can mark evidence verified.</p>
      {formError && <p className="err" role="alert">{formError}</p>}
      {error && <Alert tone="error" title="Save failed">{error}</Alert>}
      {savedId && <Alert title="Saved">Reference {savedId} saved as an unverified draft. <a href={`#/ref/${savedId}`}>Open it</a>.</Alert>}
      <Select name="cand-crop" label="Crop" options={["tomato", "eggplant", "ampalaya"]} value={form.cropCode}
        onChange={(event) => set("cropCode", event.target.value)} />
      <NumberField name="cand-amount" label="Amount (MT)" value={form.amountMt === 0 ? "" : String(form.amountMt)}
        onChange={(event) => set("amountMt", Number(event.target.value))} />
      <Select name="cand-type" label="Reference type" options={[...REFERENCE_TYPE_OPTIONS]} value={form.referenceType}
        onChange={(event) => set("referenceType", event.target.value as ReferenceType)} />
      <TextField name="cand-geo" label="Geography" value={form.geography}
        onChange={(event) => set("geography", event.target.value)} />
      <TextField name="cand-period" label="Planning period" value={form.period}
        onChange={(event) => set("period", event.target.value)} />
      <TextField name="cand-source" label="Source" value={form.source}
        onChange={(event) => set("source", event.target.value)} />
      <TextField name="cand-note" label="Evidence note" value={form.evidenceNote}
        onChange={(event) => set("evidenceNote", event.target.value)} />
      <p className="row">
        <Button disabled={busy} onClick={() => void submit()}>
          {mode === "new" ? "Submit candidate" : mode === "correct" ? "Save correction" : "Create successor"}
        </Button>
      </p>
    </section>
  );
}
