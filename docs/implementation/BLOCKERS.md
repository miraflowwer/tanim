# TANIM Member 3 blockers and release gates

These are explicit environment or cross-member dependencies. They are not silently treated as complete because code is present.

## Open gates

### BLOCK-001 ? Managed PostgreSQL/PostGIS deployment configuration

- Status: Open
- Owner: Release owner / Member 3
- Needed from: Deployment owner
- Source requirement: production durable API and restricted application role
- Exact files/API: DATABASE_URL, Alembic head, PostGIS, non-owner non-superuser non-BYPASSRLS role
- Why work cannot continue safely: CI uses a disposable service; no production host, credentials, network policy, or staging database was supplied
- Temporary fixture/adapter: GitHub Actions postgis/postgis service and test-created restricted role
- Resolution: provision staging, run migration and wrong-tenant smoke, record role and readiness evidence
- Resolved in: Pending staging release

### BLOCK-002 ? Supabase Auth/JWKS environment

- Status: Open
- Owner: Deployment owner / Member 3
- Needed from: Supabase project owner
- Source requirement: external identity boundary
- Exact files/API: SUPABASE_JWKS_URL or SUPABASE_JWT_SECRET, issuer, audience, durable users.provider_subject
- Why work cannot continue safely: real token validation cannot be demonstrated without the issuer and a provisioned durable user
- Temporary fixture/adapter: development auth remains limited to explicit in-memory mode; production rejects dev tokens
- Resolution: configure staging issuer/JWKS, provision test user and membership, run invalid/expired/wrong-tenant smoke
- Resolved in: Pending staging release

### BLOCK-003 ? Frontend integration and responsive smoke

- Status: Open
- Owner: Members 1 and 2 with Member 3 contract support
- Needed from: M1/M2 integration branch owners
- Source requirement: desktop/mobile integration evidence for every owned matrix row
- Exact files/API: app client calls against the versioned production API
- Why work cannot continue safely: Member 3 intentionally did not edit frontend feature directories
- Temporary fixture/adapter: existing in-memory adapter and frozen web demo remain available
- Resolution: run preview with production OpenAPI, verify desktop and mobile flows, record any contract requests here before modifying shared files
- Resolved in: Pending integration preview

### BLOCK-004 ? Backup, restore, privacy, and ethical release approval

- Status: Open
- Owner: Release owner / operations
- Needed from: Deployment and governance owners
- Source requirement: RPO/RTO, restore rehearsal, privacy-safe location handling, production approval
- Exact files/API: docs/DEPLOYMENT.md and docs/implementation/RELEASE_CHECKLIST.md
- Why work cannot continue safely: no backup provider, encryption key, restore target, privacy review, or staging approval is configured
- Temporary fixture/adapter: documented rehearsal procedure only
- Resolution: complete encrypted backup verification, quarterly restore drill, privacy review, and signed staging approval
- Resolved in: Pending release approval

## Closed contract decisions

- No frontend contract blocker is hidden: implemented endpoints are listed in API_REQUESTS.md and unresolved UI integration remains BLOCK-003.
- No first-party password or recovery system is planned; Supabase Auth remains the identity boundary.
- The frozen web/ deployment path remains a rollback option until a separately approved cutover.