// Farmer calendar / map / privacy / notifications (§§07/09/12).
// Calendar has an agenda fallback for 320px. Map shows only the farmer's own
// farms with a list fallback — never other farmers' exact pins. Privacy keeps
// operational vs research consent separate with withdrawal where allowed.
import { useEffect, useState } from "react";
import { Alert } from "../../components/Alert";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { EmptyState } from "../../components/EmptyState";
import { Skeleton } from "../../components/Skeleton";
import { PageHeader } from "../../components/layout/Shell";
import { fetchFarms, fetchMyConsents, grantConsent, isServerError, withdrawConsent } from "../../lib/api";
import { ORG_ID } from "../../lib/store";
import type { ConsentRecord, Plan } from "../../types";

export function CalendarView({ plans }: { plans: Plan[] }) {
  const mine = [...plans].sort((a, b) => a.plantingDate.localeCompare(b.plantingDate));
  return (
    <section aria-labelledby="cal-h">
      <PageHeader title="Planting calendar" purpose="Your planting and harvest windows with status." />
      <h2 id="cal-h" className="visually-hidden">Planting calendar</h2>
      {mine.length === 0 && (
        <EmptyState title="No windows yet." actionLabel="Create planting plan" onAction={() => (location.hash = "#/plans/new")} />
      )}
      <ul className="cards">
        {mine.map((p) => (
          <li key={p.id}>
            <Card title={`${p.crop} · ${p.harvestPeriod}`}>
              <p>Planted {p.plantingDate} · {p.state}</p>
              <p className="hint">{p.areaHa} ha · {p.farm}</p>
              <p><a href={`#/plans/${p.id}`}>Open plan</a></p>
            </Card>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function FarmerMap() {
  const [names, setNames] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    fetchFarms(ORG_ID).then((rows) => {
      if (active) setNames(rows.map((f) => f.name));
    }).catch((reason: unknown) => {
      if (active) {
        setError(isServerError(reason) ? reason.message : "The map service is unavailable. Your farm list is below.");
        setNames([]);
      }
    });
    return () => { active = false; };
  }, []);
  return (
    <section aria-labelledby="map-h">
      <PageHeader title="Map" purpose="Your farms only, at exact precision where you supplied it. No other farmer's exact locations." />
      <h2 id="map-h" className="visually-hidden">Map</h2>
      {names === null && <Skeleton label="Loading map…" />}
      {error && <Alert title="Map notice">{error}</Alert>}
      {names !== null && names.length === 0 && !error && (
        <EmptyState title="No mapped farms yet." actionLabel="Add farm" onAction={() => (location.hash = "#/farms/new")} />
      )}
      {names !== null && names.length > 0 && (
        <>
          <div className="map-fallback" role="img" aria-label="Your farms, listed below. An interactive map plug-in lands here via Member 2 map components.">
            <p className="hint">Interactive map plug-in point (Member 2). List fallback below is always available.</p>
          </div>
          <ul className="cards">
            {names.map((name) => (
              <li key={name}>
                <Card title={name}>
                  <p><Button variant="secondary" onClick={() => setSelected(selected === name ? null : name)}>
                    {selected === name ? "Close details" : "View details"}
                  </Button></p>
                  {selected === name && <p className="hint">Your farm. Exact coordinates appear only when you supplied them.</p>}
                </Card>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

const OPERATIONAL_PURPOSE = "Operate your planting plans and coordination results.";
const RESEARCH_PURPOSE = "Optional research use of anonymized coordination data.";

export function PrivacyView() {
  const [consents, setConsents] = useState<ConsentRecord[] | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    fetchMyConsents(ORG_ID).then((rows) => {
      if (active) setConsents(rows);
    }).catch(() => { if (active) setConsents([]); });
    return () => { active = false; };
  }, []);
  const operational = consents?.find((c) => c.consentType === "operational");
  const research = consents?.find((c) => c.consentType === "research");
  async function toggle(kind: "operational" | "research", active: boolean) {
    setNotice(null);
    try {
      if (active) {
        await withdrawConsent(ORG_ID, kind);
      } else {
        await grantConsent(ORG_ID, kind, kind === "operational" ? OPERATIONAL_PURPOSE : RESEARCH_PURPOSE, "v1");
      }
      const rows = await fetchMyConsents(ORG_ID).catch(() => null);
      if (rows) setConsents(rows);
      setNotice(active ? `${kind} consent withdrawn.` : `${kind} consent recorded.`);
    } catch (reason: unknown) {
      setNotice(isServerError(reason) ? reason.message : "Consent could not be saved. Your choices have been kept.");
    }
  }
  return (
    <section aria-labelledby="priv-h">
      <PageHeader title="Privacy & Consent" purpose="Operational consent is required for service. Research consent is optional and withdrawable." />
      <h2 id="priv-h" className="visually-hidden">Privacy and consent</h2>
      {consents === null && <Skeleton label="Loading consent…" />}
      {consents !== null && (
        <>
          <Card title="Operational consent (required)">
            <p>{OPERATIONAL_PURPOSE}</p>
            <p className="hint">Policy v1 · {operational ? "granted" : "not recorded"}</p>
            <p><Button variant="secondary" onClick={() => toggle("operational", !!operational)}>
              {operational ? "Withdraw operational consent" : "Grant operational consent"}
            </Button></p>
          </Card>
          <Card title="Research consent (optional)">
            <p>{RESEARCH_PURPOSE}</p>
            <p className="hint">Policy v1 · {research ? "granted" : "not granted"} · declining never blocks TANIM</p>
            <p><Button variant="secondary" onClick={() => toggle("research", !!research)}>
              {research ? "Withdraw research consent" : "Grant research consent"}
            </Button></p>
          </Card>
        </>
      )}
      {notice && <p role="status">{notice}</p>}
    </section>
  );
}

export function NotificationsView() {
  return (
    <section aria-labelledby="notif-h">
      <PageHeader title="Notifications" purpose="Plan results, evidence changes, and invitations — role-safe and concise." />
      <h2 id="notif-h" className="visually-hidden">Notifications</h2>
      <Card title="Inbox">
        <p className="hint">Live notifications arrive with Member 2 notification wiring. Nothing minor is pushed.</p>
        <ul className="cards">
          <li>
            <Card title="Welcome to TANIM">
              <p>Create a planting plan to see coordination results here.</p>
              <p className="hint">Just now · unread</p>
              <p><a href="#/plans/new">Create planting plan</a></p>
            </Card>
          </li>
        </ul>
      </Card>
    </section>
  );
}
