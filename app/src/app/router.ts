import { ALL_NAVIGATION } from "./routes";
import { FARMER_ROUTE_ALIASES } from "./routes/farmer";

export interface ParsedRoute {
  route: string;
  param: string;
  rest: string[];
}

// Detail + public + error routes render without a nav entry.
const DETAIL_ROUTE_IDS = new Set([
  "result", "adjust", "crop",
  "plans", "crops", "farms", // also match nested paths below
  "login", "register", "verify-email", "forgot-password", "reset-password",
  "session-expired", "invite", "onboarding", "account", "403", "404",
]);

export const PUBLIC_ROUTES = new Set([
  "login", "register", "verify-email", "forgot-password", "reset-password",
  "session-expired", "invite",
]);

function normalize(parts: string[]): { route: string; rest: string[] } {
  // Nested farmer paths: plans/new, plans/:id, plans/:id/result,
  // plans/:id/adjust, crops/:code, farms/new, farms/:id, onboarding/*.
  if (parts[0] === "plans" && parts[1] === "new") return { route: "plan-new", rest: [] };
  if (parts[0] === "plans" && parts[2] === "result") return { route: "result", rest: [parts[1]] };
  if (parts[0] === "plans" && parts[2] === "adjust") return { route: "adjust", rest: [parts[1]] };
  if (parts[0] === "plans" && parts[1]) return { route: "plan-detail", rest: [parts[1]] };
  if (parts[0] === "crops" && parts[1]) return { route: "crop-detail", rest: [parts[1]] };
  if (parts[0] === "farms" && parts[1] === "new") return { route: "farm-new", rest: [] };
  if (parts[0] === "farms" && parts[1]) return { route: "farm-detail", rest: [parts[1]] };
  if (parts[0] === "onboarding" && parts[1]) return { route: `onboarding-${parts[1]}`, rest: parts.slice(2) };
  if (parts[0] === "invite" && parts[1]) return { route: "invite", rest: [parts[1]] };
  if (parts[0] === "account" && parts[1]) return { route: `account-${parts[1]}`, rest: [] };
  const alias = FARMER_ROUTE_ALIASES[parts[0]];
  if (alias) {
    const target = alias.split("/");
    return normalize([...target, ...parts.slice(1)]);
  }
  return { route: parts[0] || "home", rest: parts.slice(1) };
}

// Member 1 canonical routes render without a nav entry.
const KNOWN_M1_ROUTES = new Set([
  "plan-new", "plan-detail", "result", "adjust",
  "crop-detail", "farm-new", "farm-detail",
  "account-profile", "account-security",
]);

export function parseHash(hash = window.location.hash): ParsedRoute {
  const parts = hash.replace(/^#\/?/, "").split("/").filter((p) => p.length > 0);
  if (parts.length === 0) return { route: "home", param: "", rest: [] };
  // The skip link targets #main: it is a focus target, never a route.
  if (parts[0] === "main") return { route: "home", param: "", rest: [] };
  const { route, rest } = normalize(parts);
  const known = ALL_NAVIGATION.some((item) => item.id === route)
    || ALL_NAVIGATION.some((item) => item.id === parts[0])
    || DETAIL_ROUTE_IDS.has(route)
    || DETAIL_ROUTE_IDS.has(parts[0])
    || KNOWN_M1_ROUTES.has(route)
    || PUBLIC_ROUTES.has(route)
    || route.startsWith("onboarding-")
    || route === "invite";

  if (!known) return { route: "404", param: "", rest: [] };
  return { route, param: decodeURIComponent(rest[0] ?? ""), rest };
}
