# TANIM deployment

TANIM currently has a frozen hackathon deployment and a parallel production foundation. The shared Python domain in `scripts/grci.py` is the sole calculation authority.

## Vercel layout

Vercel deploys `web/` only (frozen hackathon demo). `app/` (production P0
target) is not deployed.

- `vercel.json` installs and builds the app in `web/`.
- The static build output is `web/dist`.
- `api/options.py`, `api/grci.py`, and `api/health.py` are Vercel Python entry points.
- The entry points reuse `scripts/service.py`. They do not copy GRCI formulas or evidence rules.
- Requests use committed local datasets. The deployed API does not call PSA OpenSTAT during a farmer request.

The Vercel project root should stay at the repository root (`./`). Do not set the project root to `web/`, because the Python API and datasets also belong to the deployment.

## Routes

- `GET /api/health`: service health and available crop count
- `GET /api/options`: safe crop, region, and reference choices
- `POST /api/grci`: validated TANIM calculation

The browser uses these same-origin routes. No separate API hostname or CORS setup is needed.

## Local development

Run `python scripts/service.py --serve` from the repository root. In another terminal, run `npm run dev` inside `web/`. Vite proxies `/api` to `127.0.0.1:8000`.

For the Phase A production target, run `npm run dev` inside `app/` and the FastAPI development adapter per `backend/README.md`. The UI calls the versioned FastAPI API when online. Its offline fallback displays labeled, precomputed synthetic snapshots; it does not calculate a trusted result. PostgreSQL mode is not ready to serve planning routes until those routes use the SQLAlchemy adapter.

## Release check

Before a release, run all Python tests and the frontend test and build commands. After Vercel deploys, open `/`, `/api/health`, then run the Tomato and Eggplant demo buttons.

## Environments: preview, staging, production (PRD S37)

- Preview: per pull request, disposable, synthetic or non-sensitive data only. Used to review UI and E2E smoke before merge.
- Staging: production-like, representative non-production data, migration verification, release testing. Staging must mirror production schema and run the full gate list in `docs/20-gates.md`.
- Production: real user data, production database, restricted operational access, monitored backups. Only promoted builds reach production.

Synthetic demo fixtures stay separate from real organizational calculations at every stage. A staging or production calculation must never read the demo baseline as demand.

## Secrets per environment (PRD S32)

- Secrets are environment-separated: preview, staging, and production each use their own secret set. No secret is shared across environments.
- Secrets live in managed storage only (host secret manager or CI secret store). They are never committed, never logged, and never written to client bundles.
- Required separation: database URLs, auth keys, session signing keys, backup encryption keys, error-reporting keys.
- Rotation: rotate staging and production secrets on a schedule and after any incident. Preview secrets are short-lived.

## Proposed promotion flow (PRD S36)

Flow:

- feature branch, then pull request
- lint, typecheck, unit, data checks, API integration, frontend tests, a11y smoke, build, backend audit
- preview deployment, then review
- merge to main, then staging, then production promotion

Main protection:

- Configure `main` protection and required CI checks before production promotion.
- Require at least one reviewer approval and dismiss stale approvals on new pushes.
- Disallow direct pushes and history rewrites on protected `main`.

These are target controls; the repository documentation is not evidence that GitHub settings enforce them.

## Migration test (PRD S36)

- Migrations live in `backend/alembic/versions/`. Each migration has upgrade and downgrade.
- CI runs upgrade then downgrade then upgrade on an empty staging-like database and fails closed on error.
- Staging runs every pending migration before any release test. A failed migration blocks promotion.
- Rollback keeps the previous migration chain available. If staging migration fails, production stays on the last known good revision.

## Rollback (PRD S36, S44 gate 7)

- Keep the last known good build and database snapshot tagged per release.
- Rollback is redeploy of the prior build plus restore or forward-fix per the migration downgrade path.
- After rollback, run health and readiness checks plus the production smoke test before reopening traffic.
- Record the rollback as an audit event with actor, time, target, and reason.

## Data ingestion gate (PRD S38)

Pipeline order, no shortcuts:

- official source, then source fetch
- schema validation, then normalization
- quality checks, then versioned dataset
- review and promotion, then production reference tables

Rules:

- A newly fetched dataset never replaces production evidence on arrival. Promotion requires checks plus reviewer approval.
- Version every dataset and reference. Keep the prior version until the new one is verified.
- Log source fetch, validation result, normalization version, quality outcome, reviewer, and promotion time.
- On validation or quality failure, keep serving the last verified version and raise a refresh-failure alert.

## Backups and refresh alerts (PRD S31)

Targets: RPO at most 24 hours, RTO at most 4 hours.

- Automated daily backups of the production database, encrypted, with retention documented before pilot launch.
- Quarterly restore drill on staging: restore backup, run migrations, run calculation fixtures, measure recovery time. Record the drill date and result.
- A recent backup must be verified before any production promotion (S44 gate 6).
- Failed data refreshes generate alerts to the platform operator channel with source name, last success time, error, and next retry. Context-source outage never disables the core calculation path.

## Retiring the hackathon runtime

Keep `web/`, `api/`, and `scripts/service.py` as the Vercel hackathon path until the React `app/` and FastAPI `backend/app/` run on PostgreSQL/PostGIS with durable plans, tenant isolation, consent, reviewed evidence, and passing production release gates. Migrate deployment traffic only after a staging smoke test, data migration and rollback rehearsal, and a verified mobile/desktop user flow. Remove the old path in a separate reviewed change after equivalent Tomato/Eggplant behavior and provenance are confirmed.

## Phase status

- Phase A: Foundation: architecture, API contract, domain reuse, and release automation are under validation in PR #7.
- Phase B: Durable planning: SQLAlchemy schema exists; database-backed planning routes remain to be wired.
- Phase C: Evidence: review state and eligibility are implemented in the development adapter; database persistence and operational review remain.
- Phase D: Context: geospatial and context integration remain future work.
- Phase E: Hardening: staging, backups, recovery, and production operations remain future work.
