# TANIM parallel implementation workspace

This folder is the coordination surface for the final product implementation.

The current integration baseline is `main` at `2186fbdc8979b814d5c672b68fb170157fc4af9a`. The integration branch is `feat/final-product-integration`.

## Parallel branches

- `feat/m1-farmer-frontend`: shared frontend foundation, authentication/onboarding UI, and Farmer workspace
- `feat/m2-operations-frontend`: Coordinator, Reviewer, Admin, maps/charts/context, notifications/search/history
- `feat/m3-backend-platform`: backend, PostgreSQL/PostGIS, APIs, ingestion, security/operations, and release

## Coordination files

- [OWNERSHIP.md](OWNERSHIP.md): default file ownership and conflict rules
- [API_REQUESTS.md](API_REQUESTS.md): frontend-to-backend contract requests
- [DECISIONS.md](DECISIONS.md): cross-member architecture and product decisions
- [BLOCKERS.md](BLOCKERS.md): integration blockers that need another owner
- [TRACEABILITY_STATUS.md](TRACEABILITY_STATUS.md): implementation completion status

## Rules

1. Work on the member branch or a short-lived sub-branch. Do not develop directly on `main`.
2. Keep feature code in feature-local modules. Avoid turning `app/src/App.tsx`, `app/src/lib/api.ts`, or `app/src/types.ts` into shared conflict zones.
3. The browser never implements trusted GRCI calculation or evidence eligibility.
4. When a frontend API is missing, record the contract in `API_REQUESTS.md` instead of inventing server behavior.
5. Mobile behavior is part of feature completion, not a later polish pass.
6. Rebase or merge the integration branch regularly rather than waiting until the end.
