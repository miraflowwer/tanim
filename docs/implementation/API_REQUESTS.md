# TANIM API requests

Use this file for frontend requirements that cannot be satisfied by the current versioned API.

Do not add browser-side business logic as a substitute for a missing backend contract.

## Status values

- Proposed
- Accepted
- Modified
- Rejected
- Implemented

## Request template

```md
### API-XXX — Short name

- Status: Proposed
- Requester: Member 1 | Member 2
- Source requirement:
- Method and path:
- Authorized roles:
- Tenant scope:
- Request fields:
- Response fields:
- Validation and error states:
- Privacy constraints:
- Existing endpoint considered:
- Why the existing endpoint is insufficient:
- Backend owner note:
- Implemented in:
```

## Requests

### API-M2-001 — Organization member directory

- Status: Proposed
- Requester: Member 2
- Source requirement: 11 Admin Members list
- Method and path: GET /api/v1/organizations/{org_id}/members
- Authorized roles: org_admin, platform_admin
- Tenant scope: organization
- Request fields: org_id path
- Response fields: members[] with id, role, membership state
- Validation and error states: 403 for non-admin roles; 404 for unknown organization
- Privacy constraints: member emails only where the viewer is authorized
- Existing endpoint considered: PUT/DELETE /api/v1/organizations/{org_id}/members/{member_id}
- Why the existing endpoint is insufficient: role change and removal exist, but no list endpoint feeds the Members screen
- Backend owner note:
- Implemented in:

### API-M2-002 — Organization invitations

- Status: Proposed
- Requester: Member 2
- Source requirement: 11 Admin Invitations
- Method and path: POST /api/v1/organizations/{org_id}/invitations; POST /api/v1/invitations/{id}/resend; POST /api/v1/invitations/{id}/revoke
- Authorized roles: org_admin, platform_admin
- Tenant scope: organization
- Request fields: recipient, role, expiry
- Response fields: invitation id, role, created, expiry, status
- Validation and error states: 422 for platform_admin assignment; 404 for unknown invitation
- Privacy constraints: invitation recipient stays organization-scoped
- Existing endpoint considered: none
- Why the existing endpoint is insufficient: no invitation lifecycle exists server-side
- Backend owner note:
- Implemented in:

### API-M2-003 — Persisted organization settings

- Status: Proposed
- Requester: Member 2
- Source requirement: 11 Organization Settings
- Method and path: GET/PATCH /api/v1/organizations/{org_id}/settings
- Authorized roles: org_admin read; platform_admin write where approved
- Tenant scope: organization
- Request fields: organization name, default geography
- Response fields: the same persisted settings plus version
- Validation and error states: 403 for unauthorized roles
- Privacy constraints: settings carry no personal data
- Existing endpoint considered: none
- Why the existing endpoint is insufficient: no settings resource exists server-side
- Backend owner note:
- Implemented in:

### API-M2-004 — Canonical consent policy text

- Status: Proposed
- Requester: Member 2
- Source requirement: 11 Consent Policy read view
- Method and path: GET /api/v1/consent-policies/current
- Authorized roles: any organization member read-only
- Tenant scope: global read
- Request fields: none
- Response fields: operational policy text, research policy text, purpose, version
- Validation and error states: none beyond auth
- Privacy constraints: policy text only, no per-user records
- Existing endpoint considered: GET /api/v1/consents/me
- Why the existing endpoint is insufficient: per-user consents exist, but the canonical policy text has no read endpoint
- Backend owner note:
- Implemented in:

### API-M2-005 — Notification inbox delivery

- Status: Proposed
- Requester: Member 2
- Source requirement: 12 Notification Inbox
- Method and path: GET /api/v1/notifications; PATCH /api/v1/notifications/{id}/read
- Authorized roles: any organization member, role-filtered content
- Tenant scope: organization, role-safe rows only
- Request fields: none; read flag on patch
- Response fields: title, reason, time, read state, related object link, status text
- Validation and error states: 403 for objects outside the viewer role
- Privacy constraints: no unauthorized objects, no exact farm coordinates
- Existing endpoint considered: GET /api/v1/observability/calculations
- Why the existing endpoint is insufficient: observability rows are privileged aggregates, not role-safe deliveries
- Backend owner note:
- Implemented in:

### API-M2-006 — Authorized global search

- Status: Proposed
- Requester: Member 2
- Source requirement: 12 Global search
- Method and path: GET /api/v1/search?q=&org_id=
- Authorized roles: any organization member, role-filtered results
- Tenant scope: organization
- Request fields: query, organization scope
- Response fields: typed hits with human-readable name, subtitle, direct route
- Validation and error states: 403 never leaks; empty query returns empty list
- Privacy constraints: unauthorized objects never appear in results
- Existing endpoint considered: per-resource list endpoints
- Why the existing endpoint is insufficient: no single authorized search across crops, plans, references, and sources
- Backend owner note:
- Implemented in:
