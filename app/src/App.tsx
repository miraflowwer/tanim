import { useCallback, useEffect, useState } from "react";
import { COORDINATOR_NAVIGATION, FARMER_NAVIGATION } from "./app/routes";
import { PUBLIC_ROUTES, parseHash } from "./app/router";
import { ACCESS_TOKEN_KEY } from "./lib/api";
import { CROPS, seedClimate, seedHealth, seedPlans, seedPrices, seedReferences } from "./lib/store";
import { offlineSnapshotFor } from "./lib/fixtures";
import { fetchMyRole, fetchReferences, isServerError, transitionReference } from "./lib/api";
import { AdjustView, Home, MyPlans, NewPlan, Profile, ResultView } from "./views/farmer";
import { CropDetail, DataHealth, Overview, PlansList, ReferencesView } from "./views/coordinator";
import { AccountProfile, AccountSecurity, Forbidden, ForgotPassword, Login, NotFound, Register, ResetPassword, SessionExpired, VerifyEmail } from "./features/auth/auth.views";
import { InviteAccept, OnboardingConsent, OnboardingFarm, OnboardingOrganization } from "./features/onboarding/onboarding.views";
import { FarmDetail, FarmNew, FarmsList } from "./features/farms/farms.views";
import { PlanDetail } from "./features/plans/plan-detail.views";
import { CropDetailView, CropExplorer } from "./features/crops/crops.views";
import { CalendarView, FarmerMap, NotificationsView, PrivacyView } from "./features/farmer/farmer-extra.views";
import { AppShell, FarmerBottomNav, PublicShell, RoleDrawer } from "./components/layout/Shell";
import type { CalculateResponse, Plan, ReferenceRecord, Role } from "./types";

function hasSession(): boolean {
  return window.localStorage.getItem(ACCESS_TOKEN_KEY) !== null;
}

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
  const [authed, setAuthed] = useState(hasSession);
  const [prices] = useState(seedPrices);
  const [climate] = useState(seedClimate);
  const [health] = useState(seedHealth);

  useEffect(() => {
    const onHash = () => setLoc(parseHash());
    const onAuth = () => setAuthed(hasSession());
    window.addEventListener("hashchange", onHash);
    window.addEventListener("tanim:auth-changed", onAuth);
    return () => {
      window.removeEventListener("hashchange", onHash);
      window.removeEventListener("tanim:auth-changed", onAuth);
    };
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
    if (authed) refreshSession();
    window.addEventListener("tanim:auth-changed", refreshSession);
    return () => {
      active = false;
      window.removeEventListener("tanim:auth-changed", refreshSession);
    };
  }, [authed]);

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

  // Public + onboarding routes never show authenticated navigation.
  if (PUBLIC_ROUTES.has(route) || route.startsWith("onboarding-")) {
    return (
      <PublicShell>
        {route === "login" && <Login />}
        {route === "register" && <Register />}
        {route === "verify-email" && <VerifyEmail />}
        {route === "forgot-password" && <ForgotPassword />}
        {route === "reset-password" && <ResetPassword />}
        {route === "session-expired" && <SessionExpired />}
        {route === "invite" && <InviteAccept token={param} />}
        {route === "onboarding-organization" && <OnboardingOrganization />}
        {route === "onboarding-consent" && <OnboardingConsent />}
        {route === "onboarding-farm" && <OnboardingFarm />}
        <p className="hint" aria-live="polite">Demo data is synthetic and labeled where shown.</p>
      </PublicShell>
    );
  }

  // Account routes live outside role navigation.
  if (route === "account-profile" || route === "account-security" || route === "403" || route === "404") {
    return (
      <PublicShell>
        {route === "account-profile" && <AccountProfile />}
        {route === "account-security" && <AccountSecurity />}
        {route === "403" && <Forbidden />}
        {route === "404" && <NotFound />}
      </PublicShell>
    );
  }

  // Profile is role-agnostic and hoisted above the role split so a
  // farmer->reviewer transition never unmounts it mid-interaction
  // (its sign-in status notice must survive the shell change).
  if (route === "profile") {
    const farmerNav = role === "farmer";
    return (
      <AppShell navLabel={farmerNav ? "Farmer" : "Coordinator"}
        nav={farmerNav ? FARMER_NAVIGATION : COORDINATOR_NAVIGATION} current={route}
        topbarExtra={!farmerNav ? (
          <RoleDrawer label="Coordinator menu" role="Coordinator" org="Coop Demo Org"
            items={COORDINATOR_NAVIGATION} current={route} />
        ) : undefined}
        bottomNav={farmerNav ? <FarmerBottomNav items={FARMER_NAVIGATION} current={route} /> : undefined}>
        <Profile />
        <p className="hint" aria-live="polite">Demo data is synthetic and labeled where shown.</p>
      </AppShell>
    );
  }

  const plan = param ? plans.find((item) => item.id === param) : undefined;
  const cropEntry = CROPS.find((crop) => crop.code === (param || "tomato"));
  const isFarmerRoute = FARMER_NAVIGATION.some((item) => item.id === route)
    || ["plan-new", "plan-detail", "result", "adjust", "crop-detail", "farm-new", "farm-detail"].includes(route);
  const farmerNav = role === "farmer";

  // One role menu at a time (§02): farmers never see coordinator menus.
  if (!isFarmerRoute || !farmerNav) {
    return (
      <AppShell navLabel={farmerNav ? "Farmer" : "Coordinator"}
        nav={farmerNav ? FARMER_NAVIGATION : COORDINATOR_NAVIGATION} current={route}
        topbarExtra={!farmerNav ? (
          <RoleDrawer label="Coordinator menu" role="Coordinator" org="Coop Demo Org"
            items={COORDINATOR_NAVIGATION} current={route} />
        ) : undefined}
        bottomNav={farmerNav ? <FarmerBottomNav items={FARMER_NAVIGATION} current={route} /> : undefined}>
        {route === "overview" && <Overview />}
        {route === "plans" && !farmerNav && <PlansList plans={plans} />}
        {route === "crop" && cropEntry && (
          <CropDetail cropCode={cropEntry.code} cropName={cropEntry.name}
            prices={prices} climate={climate} />
        )}
        {route === "references" && <ReferencesView refs={refs} role={role} onTransition={transition} error={referenceError} />}
        {route === "data" && <DataHealth sources={health} />}
        <p className="hint" aria-live="polite">Demo data is synthetic and labeled where shown.</p>
      </AppShell>
    );
  }

  return (
    <AppShell navLabel="Farmer" nav={FARMER_NAVIGATION} current={route}
      bottomNav={<FarmerBottomNav items={FARMER_NAVIGATION} current={route} />}>
      {route === "home" && <Home plans={plans} />}
      {route === "plans" && <MyPlans plans={plans} />}
      {route === "plan-new" && <NewPlan onSavePlan={savePlan} />}
      {route === "plan-detail" && <PlanDetail planId={param} latest={param ? results[param] : undefined} />}
      {route === "privacy" && <PrivacyView />}
      {route === "crops" && <CropExplorer />}
      {route === "crop-detail" && <CropDetailView cropCode={param} />}
      {route === "calendar" && <CalendarView plans={plans} />}
      {route === "map" && <FarmerMap />}
      {route === "farms" && <FarmsList />}
      {route === "farm-new" && <FarmNew />}
      {route === "farm-detail" && <FarmDetail farmId={param} />}
      {route === "notifications" && <NotificationsView />}
      {route === "result" && plan && (
        <ResultView plan={plan} result={results[plan.id]} prices={prices} climate={climate} />
      )}
      {route === "result" && !plan && <p role="alert">Plan not found. <a href="#/plans">Back to My Plans</a>.</p>}
      {route === "adjust" && plan && <AdjustView plan={plan} onUpdatePlan={updatePlan} />}
      <p className="hint" aria-live="polite">Demo data is synthetic and labeled where shown.</p>
    </AppShell>
  );
}
