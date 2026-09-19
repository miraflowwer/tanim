import { useCallback, useEffect, useState } from "react";
import { ADMIN_NAVIGATION, COORDINATOR_NAVIGATION, FARMER_NAVIGATION, GLOBAL_NAVIGATION, REVIEWER_NAVIGATION } from "./app/routes";
import { parseHash } from "./app/router";
import { CROPS, seedClimate, seedHealth, seedPlans, seedPrices, seedReferences } from "./lib/store";
import { offlineSnapshotFor } from "./lib/fixtures";
import { fetchMyRole, fetchReferences, isServerError, transitionReference } from "./lib/api";
import { AdjustView, Home, MyPlans, NewPlan, Profile, ResultView } from "./views/farmer";
import { CropDetail, DataHealth, Overview, PlansList, ReferencesView } from "./views/coordinator";
import { AttentionQueue, CoordinatorPlanDetail } from "./features/coordination/coordination.views";
import { CoordinatorMap, CoordinatorTimeline, HarvestConcentration, SupplyVsReference } from "./features/context/context.views";
import { CandidateForm, ReferenceDetail, ReviewQueue } from "./features/evidence/evidence.views";
import { AdminHome, AuditLog, CalculationPolicy, ConsentPolicy, ExportCenter, Invitations, Members, OrganizationSettings } from "./features/organization/organization.views";
import { NotificationsInbox } from "./features/notifications/notifications.views";
import { GlobalSearch } from "./features/search/search.views";
import { CalculationHistory } from "./features/history/history.views";
import type { CalculateResponse, Plan, ReferenceRecord, Role } from "./types";

export default function App() {
  const initialPlans = seedPlans();
  const [{ route, param }, setLoc] = useState(parseHash);
  const [plans, setPlans] = useState<Plan[]>(initialPlans);
  const [results, setResults] = useState<Record<string, CalculateResponse>>(() => Object.fromEntries(
    initialPlans.flatMap((plan) => {
      const result = offlineSnapshotFor(plan);
      return result ? [[plan.id, result]] : [];
    }),
  ));
  const [refs, setRefs] = useState<ReferenceRecord[]>(seedReferences);
  const [referenceError, setReferenceError] = useState<string | null>(null);
  const [role, setRole] = useState<Role>("farmer");
  const [prices] = useState(seedPrices);
  const [climate] = useState(seedClimate);
  const [health] = useState(seedHealth);

  useEffect(() => {
    const onHash = () => setLoc(parseHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    let active = true;
    let generation = 0;
    function refreshSession() {
      const current = ++generation;
      fetchMyRole("org-1").then((nextRole) => {
        if (active && generation === current) setRole(nextRole);
      }).catch(() => { if (active && generation === current) setRole("farmer"); });
      fetchReferences("org-1").then((records) => {
        if (active && generation === current) {
          setRefs(records);
          setReferenceError(null);
        }
      }).catch((reason: unknown) => {
        if (active && generation === current) setReferenceError(isServerError(reason) ? reason.message : "The reference API is unavailable.");
      });
    }
    refreshSession();
    window.addEventListener("tanim:auth-changed", refreshSession);
    return () => {
      active = false;
      window.removeEventListener("tanim:auth-changed", refreshSession);
    };
  }, []);

  const savePlan = useCallback((plan: Plan, result?: CalculateResponse) => {
    setPlans((previous) => [...previous, plan]);
    if (result) setResults((previous) => ({ ...previous, [plan.id]: result }));
  }, []);
  const updatePlan = useCallback((plan: Plan, result: CalculateResponse) => {
    setPlans((previous) => previous.map((item) => (item.id === plan.id ? plan : item)));
    setResults((previous) => ({ ...previous, [plan.id]: result }));
  }, []);
  const transition = useCallback(async (
    id: string,
    next: "under_review" | "verified" | "rejected" | "draft" | "expired",
  ) => {
    try {
      const updated = await transitionReference(id, next);
      setRefs((previous) => previous.map((reference) => reference.id === id ? updated : reference));
      setReferenceError(null);
    } catch (reason: unknown) {
      setReferenceError(isServerError(reason) ? reason.message : "The review API is unavailable.");
    }
  }, []);

  const plan = param ? plans.find((item) => item.id === param) : undefined;
  const cropEntry = CROPS.find((crop) => crop.code === (param || "tomato"));

  return (
    <div className="app">
      <a className="skip" href="#main">Skip to main content</a>
      <header className="topbar">
        <h1>TANIM</h1>
        <p>Timely Agricultural Network for Informed Market</p>
      </header>
      <nav className="tabs" aria-label="Farmer">
        {FARMER_NAVIGATION.map((item) => (
          <a key={item.id} href={item.href} aria-current={route === item.id ? "page" : undefined}>{item.label}</a>
        ))}
      </nav>
      <nav className="tabs" aria-label="Coordinator">
        {COORDINATOR_NAVIGATION.map((item) => (
          <a key={item.id} href={item.href} aria-current={route === item.id ? "page" : undefined}>{item.label}</a>
        ))}
      </nav>
      {role === "reviewer" && (
        <nav className="tabs" aria-label="Reviewer">
          {REVIEWER_NAVIGATION.map((item) => (
            <a key={item.id} href={item.href} aria-current={route === item.id ? "page" : undefined}>{item.label}</a>
          ))}
        </nav>
      )}
      {role === "admin" && (
        <nav className="tabs" aria-label="Admin">
          {ADMIN_NAVIGATION.map((item) => (
            <a key={item.id} href={item.href} aria-current={route === item.id ? "page" : undefined}>{item.label}</a>
          ))}
        </nav>
      )}
      <nav className="tabs" aria-label="Global">
        {GLOBAL_NAVIGATION.map((item) => (
          <a key={item.id} href={item.href} aria-current={route === item.id ? "page" : undefined}>{item.label}</a>
        ))}
      </nav>
      <main id="main" tabIndex={-1}>
        {route === "home" && <Home plans={plans} />}
        {route === "my" && <MyPlans plans={plans} />}
        {route === "new" && <NewPlan onSavePlan={savePlan} />}
        {route === "profile" && <Profile />}
        {route === "result" && plan && (
          <ResultView plan={plan} result={results[plan.id]} prices={prices} climate={climate} />
        )}
        {route === "result" && !plan && <p role="alert">Plan not found. <a href="#/my">Back to My Plans</a>.</p>}
        {route === "adjust" && plan && <AdjustView plan={plan} onUpdatePlan={updatePlan} />}
        {route === "overview" && <Overview />}
        {route === "plans" && <PlansList plans={plans} />}
        {route === "crop" && cropEntry && (
          <CropDetail cropCode={cropEntry.code} cropName={cropEntry.name}
            prices={prices} climate={climate} />
        )}
        {route === "references" && <ReferencesView refs={refs} role={role} onTransition={transition} error={referenceError} />}
        {route === "data" && <DataHealth sources={health} />}
        {route === "attention" && <AttentionQueue />}
        {route === "cplan" && param && <CoordinatorPlanDetail planId={param} />}
        {route === "cplan" && !param && <p role="alert">Plan not found. <a href="#/plans">Back to Plans</a>.</p>}
        {route === "map" && <CoordinatorMap />}
        {route === "timeline" && (
          <>
            <CoordinatorTimeline />
            <HarvestConcentration />
          </>
        )}
        {route === "review" && <ReviewQueue role={role} />}
        {route === "ref" && param && <ReferenceDetail refId={param} role={role} />}
        {route === "ref" && !param && <p role="alert">Reference not found. <a href="#/review">Back to Review queue</a>.</p>}
        {route === "refnew" && <CandidateForm mode="new" />}
        {route === "admin" && <AdminHome />}
        {route === "members" && <Members />}
        {route === "invitations" && <Invitations />}
        {route === "organization" && <OrganizationSettings />}
        {route === "audit" && <AuditLog />}
        {route === "exports" && <ExportCenter />}
        {route === "policy" && <CalculationPolicy />}
        {route === "consent" && <ConsentPolicy />}
        {route === "notifications" && <NotificationsInbox />}
        {route === "search" && <GlobalSearch plans={plans} role={role} />}
        {route === "history" && param && <CalculationHistory planId={param} />}
        {route === "history" && !param && <p role="alert">Plan not found. <a href="#/my">Back to My Plans</a>.</p>}
        {route === "crop" && cropEntry && <SupplyVsReference cropCode={cropEntry.code} />}
        <p className="hint" aria-live="polite">Demo data is synthetic and labeled where shown.</p>
      </main>
      <footer>
        <p className="hint">Review controls follow the signed-in API role ({role}). FastAPI verifies permissions for every action.</p>
        <p className="hint">Crop detail: <a href="#/crop/tomato">Tomato</a> · <a href="#/crop/eggplant">Eggplant</a></p>
      </footer>
    </div>
  );
}
