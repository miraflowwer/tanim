# TANIM branch-ready release checklist

## Code and contract

- [ ] Current branch is feat/m3-backend-platform and has one pull request.
- [ ] No Member 1 or Member 2 feature directory changed without an explicit contract fix.
- [ ] Production routes use the repository boundary and no global store import.
- [ ] scripts/grci.py remains the sole calculation authority.
- [ ] openapi/openapi.json matches the production FastAPI app.
- [ ] API_REQUESTS.md and TRACEABILITY_STATUS.md include final PR evidence.

## Automated verification

- [ ] Ruff passes.
- [ ] pytest passes for backend and repository tests.
- [ ] OpenAPI check passes.
- [ ] Bandit and pip-audit pass.
- [ ] Frontend contract, build, browser, accessibility, and fallback-web checks pass.
- [ ] PostgreSQL/PostGIS upgrade -> downgrade -> upgrade passes.
- [ ] Restricted application role passes readiness, wrong-tenant, RLS, and append-only tests.
- [ ] Ingestion, provenance, auth, headers, rate-limit, request-ID, safe-log, pagination, and stale/unavailable tests pass.

## Preview and staging

- [ ] Preview health/readiness smoke passes.
- [ ] Supabase staging issuer/JWKS and provisioned durable test user are configured.
- [ ] Desktop and mobile integration smoke is recorded by M1/M2.
- [ ] Staging migration and rollback rehearsal are recorded.
- [ ] Privacy and exact-coordinate handling are reviewed.
- [ ] Encrypted backup is verified and a restore rehearsal result is recorded.

## Production approval

- [ ] Host, database, secrets, restricted role, monitoring, and backup retention are configured.
- [ ] Release owner approves the staging evidence.
- [ ] Rollback target and frozen web fallback are available.
- [ ] Production cutover is approved in a separate change.