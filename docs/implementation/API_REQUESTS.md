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

### API-001 — Production account lifecycle (register/verify/recovery)

- Status: Proposed
- Requester: Member 1
- Source requirement: `05_AUTH_ACCOUNT_AND_SESSION_LIFECYCLE.md`
- Method and path: `POST /api/v1/auth/register`, `POST /api/v1/auth/verify`, `POST /api/v1/auth/recovery/request`, `POST /api/v1/auth/recovery/reset`
- Authorized roles: unauthenticated (register/recovery request), token-bound (verify/reset)
- Tenant scope: global identity; organization assigned at onboarding, never self-selected Reviewer/Admin
- Request fields: register `{full_name, email, password}`, verify `{token}`, recovery request `{email}`, reset `{token, new_password}`
- Response fields: generic messages; recovery request never reveals whether an email exists; tokens expire
- Validation and error states: `VALIDATION_ERROR`, `UNAUTHORIZED` (invalid/expired token), `SERVICE_UNAVAILABLE`; resend available for verify
- Privacy constraints: no role elevation through the client; no plaintext/weak password storage
- Existing endpoint considered: `POST /api/v1/auth/session` (dev-only `user_id` exchange)
- Why the existing endpoint is insufficient: dev helper cannot create, verify, or recover real accounts
- Backend owner note:
- Implemented in:

### API-002 — Session lifecycle (refresh/revoke/sign-out-all)

- Status: Proposed
- Requester: Member 1
- Source requirement: `05_AUTH_ACCOUNT_AND_SESSION_LIFECYCLE.md`
- Method and path: `POST /api/v1/auth/refresh`, `POST /api/v1/auth/sign-out`, `POST /api/v1/auth/sign-out-all`
- Authorized roles: authenticated user (own sessions only)
- Tenant scope: global identity
- Request fields: refresh `{}`, sign-out-all `{}`
- Response fields: refresh `{access_token}`, sign-out-all `{revoked_count}`
- Validation and error states: `UNAUTHORIZED` (expired/revoked), expired-session return path to a safe intended route
- Privacy constraints: minimal session detail (no unnecessary IP/device exposure)
- Existing endpoint considered: `POST /api/v1/auth/session`, `GET /api/v1/me`
- Why the existing endpoint is insufficient: no refresh, revoke, or sign-out-all semantics
- Backend owner note:
- Implemented in:

### API-003 — Account profile and email change

- Status: Proposed
- Requester: Member 1
- Source requirement: `05_AUTH_ACCOUNT_AND_SESSION_LIFECYCLE.md`
- Method and path: `GET /api/v1/account/profile`, `PATCH /api/v1/account/profile`, `POST /api/v1/account/email-change`, `POST /api/v1/account/email-verify`
- Authorized roles: authenticated user (own account only)
- Tenant scope: global identity
- Request fields: profile `{display_name}`, email change `{new_email}`, email verify `{token}`
- Response fields: profile `{display_name, email, email_verified}`
- Validation and error states: `VALIDATION_ERROR`, `UNAUTHORIZED`
- Privacy constraints: email change requires verification on the new address before it takes effect
- Existing endpoint considered: `GET /api/v1/me`
- Why the existing endpoint is insufficient: read-only identity snapshot, no profile/email mutation
- Backend owner note:
- Implemented in:

### API-004 — Organization onboarding and invitations

- Status: Proposed
- Requester: Member 1
- Source requirement: `06_ORGANIZATION_ONBOARDING_AND_INVITATIONS.md`
- Method and path: `POST /api/v1/organizations`, `POST /api/v1/organizations/join`, `GET /api/v1/invites/{token}`, `POST /api/v1/invites/{token}/accept`, `POST /api/v1/invites/{token}/decline`
- Authorized roles: authenticated user; invite detail may be public with token but must not leak membership
- Tenant scope: creates/assigns organization membership; default self-service role Farmer
- Request fields: create `{name, region, municipality?}`, join `{code}`, accept/decline `{}`
- Response fields: invite `{organization, role, expires_at, state}`, membership `{organization_id, role}`
- Validation and error states: expired/revoked/already-used/wrong-account states stay visible, never silent
- Privacy constraints: cannot invite Platform Admin; role tampering rejected server-side
- Existing endpoint considered: none (no org/invite endpoints in the current API)
- Why the existing endpoint is insufficient: no organization or invitation surface exists yet
- Backend owner note:
- Implemented in:

### API-005 — Farmer plan history depth (calculation descriptors)

- Status: Proposed
- Requester: Member 1
- Source requirement: `07_FARMER_WORKSPACE.md` (Calculations tab), `12_NOTIFICATIONS_SEARCH_AND_HISTORY.md`
- Method and path: `GET /api/v1/plans/{plan_id}/calculations`
- Authorized roles: Farmer (own plans), Coordinator where authorized
- Tenant scope: organization plan
- Request fields: none
- Response fields: `[{calculation_id, revision_number, timestamp, engine_version, policy_version, status, expected_production_mt, coordination_state}]`
- Validation and error states: `PERMISSION_DENIED`, `SERVICE_UNAVAILABLE`
- Privacy constraints: farmer-scoped; no cross-farmer leakage
- Existing endpoint considered: `GET /api/v1/plans/{plan_id}/revisions`, `GET /api/v1/calculations/{calculation_id}`
- Why the existing endpoint is insufficient: revisions lack per-run calculation descriptors; single-calculation fetch requires knowing each ID
- Backend owner note:
- Implemented in:
