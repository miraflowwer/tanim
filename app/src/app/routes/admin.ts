import type { NavigationItem } from "./types";

// Organization-admin routes are added by the Admin feature without editing App.tsx.
export const ADMIN_NAVIGATION: NavigationItem[] = [
  { id: "admin", label: "Admin", area: "admin", href: "#/admin" },
  { id: "members", label: "Members", area: "admin", href: "#/members" },
  { id: "invitations", label: "Invitations", area: "admin", href: "#/invitations" },
  { id: "organization", label: "Organization", area: "admin", href: "#/organization" },
  { id: "audit", label: "Audit", area: "admin", href: "#/audit" },
  { id: "exports", label: "Exports", area: "admin", href: "#/exports" },
  { id: "policy", label: "Policy", area: "admin", href: "#/policy" },
  { id: "consent", label: "Consent policy", area: "admin", href: "#/consent" },
];
