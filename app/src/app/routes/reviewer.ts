import type { NavigationItem } from "./types";

// Reviewer routes are added by the Reviewer feature without editing App.tsx.
export const REVIEWER_NAVIGATION: NavigationItem[] = [
  { id: "review", label: "Review queue", area: "reviewer", href: "#/review" },
  { id: "refnew", label: "Submit reference", area: "reviewer", href: "#/refnew" },
  { id: "references", label: "References", area: "reviewer", href: "#/references" },
];
