# TANIM parallel implementation workspace

This folder is the coordination surface for the final product implementation. The Member 3 work is being completed on feat/m3-backend-platform from the bootstrap branch.

## Parallel branches

- feat/m1-farmer-frontend: shared frontend foundation, authentication/onboarding UI, and Farmer workspace
- feat/m2-operations-frontend: Coordinator, Reviewer, Admin, maps/charts/context, notifications/search/history
- feat/m3-backend-platform: backend, PostgreSQL/PostGIS, APIs, ingestion, security/operations, and release

## Coordination files

- OWNERSHIP.md: default file ownership and conflict rules
- API_REQUESTS.md: frontend-to-backend contract ledger
- DECISIONS.md: cross-member architecture decisions
- BLOCKERS.md: environment and cross-member release gates
- TRACEABILITY_STATUS.md: evidence matrix for Member 3 and integration status

## Rules

1. Work on a feature branch and open one reviewable pull request.
2. Keep Member 1 and Member 2 feature directories unchanged unless a contract fix is explicitly agreed.
3. Production routes use the repository boundary and never use the global demo store.
4. The browser never implements trusted GRCI calculation or evidence eligibility.
5. Mobile and desktop integration evidence is recorded separately from backend implementation.
6. Keep the frozen web/ path until the production cutover gates are approved.