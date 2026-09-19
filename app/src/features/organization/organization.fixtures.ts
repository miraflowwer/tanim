import type { InvitationRow, MemberRow } from "./organization.api";

// Typed fixtures for surfaces without a backend contract yet. Every fixture
// is labeled synthetic and tracked in docs/implementation/API_REQUESTS.md.
// Fixtures never stand in for a production success path.
export const MEMBER_FIXTURE_NOTE =
  "Member directory is a typed fixture. The live member list needs API-M2-001.";

export function seedMembers(): MemberRow[] {
  return [
    { id: "farmer-1", role: "farmer", state: "active" },
    { id: "reviewer-1", role: "reviewer", state: "active" },
    { id: "admin-1", role: "org_admin", state: "active" },
  ];
}

export const INVITATION_FIXTURE_NOTE =
  "Invitations are a typed fixture. Sending and accepting invitations needs API-M2-002.";

export function seedInvitations(): InvitationRow[] {
  return [
    {
      id: "invite-seed-1", role: "coordinator", created: "2026-09-18",
      expiry: "2026-09-25", status: "pending (fixture)",
    },
  ];
}

export const ORGANIZATION_FIXTURE_NOTE =
  "Organization settings are a typed fixture. Persisted settings need API-M2-003.";

export interface OrganizationFixture {
  name: string;
  defaultGeography: string;
}

export function seedOrganization(): OrganizationFixture {
  return { name: "Coop Demo Org", defaultGeography: "CALABARZON" };
}

export const CONSENT_POLICY_FIXTURE =
  "Operational consent covers coordination use of plans. Research consent is separate and optional. " +
  "Administrators cannot grant research consent for another person. Policy text fixture; canonical policy needs API-M2-004.";
