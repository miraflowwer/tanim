import { useEffect, useState } from "react";
import { Alert } from "../../components/Alert";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { DataTable } from "../../components/DataTable";
import { EmptyState } from "../../components/EmptyState";
import { Select } from "../../components/Select";
import { Skeleton } from "../../components/Skeleton";
import { Status } from "../../components/Status";
import { TextField } from "../../components/TextField";
import { ORG_ID } from "../../lib/store";
import {
  changeMemberRole,
  createExport,
  fetchAudit,
  fetchPolicy,
  isServerError,
  removeMember,
  type AuditRow,
  type PolicyRecord,
} from "./organization.api";
import {
  CONSENT_POLICY_FIXTURE,
  INVITATION_FIXTURE_NOTE,
  MEMBER_FIXTURE_NOTE,
  ORGANIZATION_FIXTURE_NOTE,
  seedInvitations,
  seedMembers,
  seedOrganization,
} from "./organization.fixtures";

const MEMBER_ROLES = ["farmer", "coordinator", "reviewer", "org_admin"];

export function AdminHome() {
  return (
    <section aria-labelledby="admin-h">
      <h2 id="admin-h">Admin home</h2>
      <ul className="cards">
        {[
          ["Members", "Roles and membership state.", "#/members"],
          ["Invitations", "Pending invitations and expiry.", "#/invitations"],
          ["Organization", "Persisted organization settings.", "#/organization"],
          ["Audit", "Who did what, and when.", "#/audit"],
          ["Exports", "Recorded data exports.", "#/exports"],
          ["Policy", "Calculation policy versions.", "#/policy"],
          ["Consent policy", "Operational and research consent rules.", "#/consent"],
        ].map(([title, body, href]) => (
          <li key={href}>
            <article className="card" aria-label={title}>
              <h3>{title}</h3>
              <p>{body}</p>
              <p><a href={href}>Open {title.toLowerCase()}</a></p>
            </article>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function Members() {
  const [members, setMembers] = useState(seedMembers());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function setRole(id: string, role: string) {
    if (role === "platform_admin") {
      setError("Platform authority cannot be assigned through an organization.");
      return;
    }
    setBusy(true);
    try {
      await changeMemberRole(ORG_ID, id, role);
      setMembers((previous) => previous.map((member) => member.id === id ? { ...member, role } : member));
      setError(null);
    } catch (reason: unknown) {
      setError(isServerError(reason) ? reason.message : "Role change failed.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    setBusy(true);
    try {
      await removeMember(ORG_ID, id);
      setMembers((previous) => previous.filter((member) => member.id !== id));
      setError(null);
    } catch (reason: unknown) {
      setError(isServerError(reason) ? reason.message : "Removal failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="members-h">
      <h2 id="members-h">Members</h2>
      <p role="note" className="badge">{MEMBER_FIXTURE_NOTE}</p>
      {error && <Alert tone="error" title="Member action failed">{error}</Alert>}
      <DataTable
        caption="Organization members"
        columns={["Member", "Role", "State"]}
        rows={members.map((member) => [member.id, member.role, member.state])}
      />
      <ul className="cards">
        {members.map((member) => (
          <li key={member.id}>
            <article className="card" aria-label={`Member ${member.id}`}>
              <h3>{member.id}</h3>
              <p className="hint">Role: {member.role} · State: {member.state}</p>
              <div className="filters" role="search" aria-label={`Change role for ${member.id}`}>
                <Select name={`role-${member.id}`} label="Role" options={MEMBER_ROLES} value={member.role}
                  onChange={(event) => void setRole(member.id, event.target.value)} />
              </div>
              <p className="row">
                <Button variant="secondary" disabled={busy} onClick={() => void remove(member.id)}>
                  Remove member
                </Button>
              </p>
            </article>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function Invitations() {
  const invitations = seedInvitations();
  return (
    <section aria-labelledby="inv-h">
      <h2 id="inv-h">Invitations</h2>
      <p role="note" className="badge">{INVITATION_FIXTURE_NOTE}</p>
      <DataTable
        caption="Pending invitations (fixture)"
        columns={["Invitation", "Role", "Created", "Expiry", "Status"]}
        rows={invitations.map((invitation) => [
          invitation.id, invitation.role, invitation.created, invitation.expiry, invitation.status,
        ])}
      />
      <p className="hint">Invite, resend, and revoke actions appear here once the backend contract lands.</p>
    </section>
  );
}

export function OrganizationSettings() {
  const organization = seedOrganization();
  return (
    <section aria-labelledby="org-h">
      <h2 id="org-h">Organization</h2>
      <p role="note" className="badge">{ORGANIZATION_FIXTURE_NOTE}</p>
      <Card title="Persisted settings preview">
        <dl>
          <dt>Organization name</dt><dd>{organization.name}</dd>
          <dt>Default geography</dt><dd>{organization.defaultGeography}</dd>
        </dl>
      </Card>
      <p className="hint">Only real persisted settings will be editable here. No local-only settings are shown.</p>
    </section>
  );
}

export function ConsentPolicy() {
  return (
    <section aria-labelledby="consent-h">
      <h2 id="consent-h">Consent policy</h2>
      <Card title="Policy text (fixture)">
        <p>{CONSENT_POLICY_FIXTURE}</p>
      </Card>
      <p className="hint">An administrator cannot grant research consent on behalf of another person.</p>
    </section>
  );
}

export function AuditLog() {
  const [rows, setRows] = useState<AuditRow[] | null>(null);
  const [action, setAction] = useState("All");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchAudit(ORG_ID).then((events) => {
      if (!active) return;
      setRows(events);
      setError(null);
    }).catch((reason: unknown) => {
      if (active) setError(isServerError(reason) ? reason.message : "The audit log is unavailable.");
    });
    return () => { active = false; };
  }, []);

  if (error) return <Alert tone="error" title="Audit unavailable">{error}</Alert>;
  if (rows === null) return <Skeleton label="Loading audit events" />;
  const actions = ["All", ...new Set(rows.map((row) => row.action))];
  const shown = rows.filter((row) => action === "All" || row.action === action);
  return (
    <section aria-labelledby="audit-h">
      <h2 id="audit-h">Audit</h2>
      <div className="filters" role="search" aria-label="Filter audit events">
        <Select name="audit-action" label="Action" options={actions} value={action}
          onChange={(event) => setAction(event.target.value)} />
      </div>
      {shown.length === 0 ? (
        <EmptyState title="No audit events" body="Events appear here as administrators act." />
      ) : (
        <ul className="cards">
          {shown.map((row) => (
            <li key={row.id}>
              <article className="card" aria-label={`Audit event ${row.action}`}>
                <h3>{row.action}</h3>
                <p className="hint">{row.time} · Actor {row.actor} · Target {row.target}</p>
                {row.summary && <p>{row.summary}</p>}
              </article>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function ExportCenter() {
  const [purpose, setPurpose] = useState("");
  const [individuals, setIndividuals] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [record, setRecord] = useState<{ id: string; planCount: number } | null>(null);

  async function create() {
    if (purpose.trim() === "") {
      setFormError("Purpose is required before an export is recorded.");
      return;
    }
    setFormError(null);
    setBusy(true);
    try {
      const created = await createExport(ORG_ID, purpose.trim(), individuals);
      setRecord({ id: created.id, planCount: created.planCount });
      setError(null);
    } catch (reason: unknown) {
      setError(isServerError(reason) ? reason.message : "Export recording failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="exports-h">
      <h2 id="exports-h">Exports</h2>
      <p className="hint">Every export is recorded with its purpose. Individual data needs administrator access.</p>
      {formError && <p className="err" role="alert">{formError}</p>}
      {error && <Alert tone="error" title="Export failed">{error}</Alert>}
      {record && (
        <Alert title="Export recorded">
          Export {record.id} recorded with {record.planCount} plans in scope. No file is downloaded from this screen.
        </Alert>
      )}
      <TextField name="export-purpose" label="Purpose" value={purpose}
        onChange={(event) => setPurpose(event.target.value)} placeholder="Why is this export needed?" />
      <p>
        <label htmlFor="export-individuals">
          <input
            id="export-individuals"
            type="checkbox"
            checked={individuals}
            onChange={(event) => setIndividuals(event.target.checked)}
          />{" "}
          Include individual records
        </label>
      </p>
      {individuals && (
        <Alert title="Privacy warning">
          Individual exports expose farmer-level records and are logged. Confirm this scope is necessary.
        </Alert>
      )}
      <p className="row">
        <Button disabled={busy} onClick={() => void create()}>Record export</Button>
      </p>
    </section>
  );
}

export function CalculationPolicy() {
  const [policy, setPolicy] = useState<PolicyRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchPolicy().then((result) => {
      if (!active) return;
      setPolicy(result);
      setError(null);
    }).catch((reason: unknown) => {
      if (active) setError(isServerError(reason) ? reason.message : "The calculation policy is unavailable.");
    });
    return () => { active = false; };
  }, []);

  if (error) return <Alert tone="error" title="Policy unavailable">{error}</Alert>;
  if (policy === null) return <Skeleton label="Loading calculation policy" />;
  return (
    <section aria-labelledby="policy-h">
      <h2 id="policy-h">Calculation policy</h2>
      <p className="hint">Read-only. Threshold changes are a platform action and always create a new version.</p>
      <Card title={`Policy ${policy.id}`}>
        <dl>
          <dt>Version</dt><dd>{policy.version}</dd>
          <dt>Elevated load above</dt><dd>{policy.elevatedLoad}</dd>
          <dt>High load above</dt><dd>{policy.highLoad}</dd>
          <dt>Created by</dt><dd>{policy.createdBy}</dd>
          <dt>Created at</dt><dd>{policy.createdAt}</dd>
        </dl>
      </Card>
      <p><Status label="Organization admins cannot change thresholds here" tone="info" /></p>
    </section>
  );
}
