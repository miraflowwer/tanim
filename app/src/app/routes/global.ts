import type { NavigationItem } from "./types";

// Global destinations are visible to every signed-in role.
export const GLOBAL_NAVIGATION: NavigationItem[] = [
  { id: "notifications", label: "Notifications", area: "global", href: "#/notifications" },
  { id: "search", label: "Search", area: "global", href: "#/search" },
];
