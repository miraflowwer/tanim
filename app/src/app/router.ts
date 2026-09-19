import { ALL_NAVIGATION } from "./routes";

export interface ParsedRoute {
  route: string;
  param: string;
}

const DETAIL_ROUTE_IDS = new Set(["result", "adjust", "crop"]);

export function parseHash(hash = window.location.hash): ParsedRoute {
  const parts = hash.replace(/^#\/?/, "").split("/");
  const id = parts[0] || "home";
  const known = ALL_NAVIGATION.some((item) => item.id === id) || DETAIL_ROUTE_IDS.has(id);

  if (!known) return { route: "home", param: "" };
  return { route: id, param: decodeURIComponent(parts[1] ?? "") };
}
