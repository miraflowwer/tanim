# PRD S44 production release gates

This is the status of PR #7's Phase A foundation, not a production release approval. A checked item needs executed evidence. CI on a disposable GitHub runner verifies code and migration behavior; it does not replace staging, operational, or privacy review.

## Review evidence

The [PR checks](https://github.com/miraflowwer/tanim/pull/7/checks) must show a completed run attached to the current head of `feat/p0-foundation`. A run marked `action_required`, cancelled, or attached only to an earlier SHA does not count as final-head verification. CI uses a fresh GitHub runner checkout and executes the Python, PostgreSQL/PostGIS, frontend/browser, hackathon-web, and live OpenSTAT jobs. The branch contains source and lockfiles only; runner installs and browser binaries are disposable.

This ledger records automation and implementation evidence for Phase A. Staging migration, restore, rollout, privacy, and ethical review gates remain open for a production release.

- [x] 1. All required foundation CI checks pass: Python, PostgreSQL/PostGIS, frontend/browser, hackathon web, and live OpenSTAT passed in [CI run 35464093454](https://github.com/miraflowwer/tanim/actions/runs/35464093454). A rewritten head must pass the same suite.
- [x] 2. Mobile and desktop browser E2E passes: 36 real Playwright tests passed, including API-backed flows, in [CI run 35464093454](https://github.com/miraflowwer/tanim/actions/runs/35464093454).
- [x] 3. Accessibility automation passes: executed axe, keyboard, focus, landmarks, errors, 200% page scale, 320/375 px, and 44 px target checks in both browser projects. This is automation evidence, not a manual accessibility review.
- [x] 4. Blocking `npm audit` for both frontends and Playwright, `pip-audit`, and Bandit passed. The sole B105 suppression is documented on the OAuth token-type literal.
- [ ] 5. Staging migration succeeds. CI upgrade/downgrade/re-upgrade against disposable PostgreSQL/PostGIS is a prerequisite, not a staging deployment.
- [ ] 6. A recent backup is verified. Record a restore drill and recovery result.
- [ ] 7. Rollback is available. Rehearse deployment and database rollback with a known good release.
- [ ] 8. Production health and readiness checks pass. Process health is implemented; PostgreSQL mode intentionally returns not ready until database-backed routes are wired.
- [x] 9. Calculation fixtures reproduce expected values. The Tomato/Eggplant fixtures and shared Python domain ran in `python -m pytest backend/tests tests -q`; 198 passed, 6 skipped in [CI run 35464093454](https://github.com/miraflowwer/tanim/actions/runs/35464093454).
- [ ] 10. Tenant isolation passes against the production mechanism. The disposable PostgreSQL RLS job must pass as a non-owner, non-BYPASSRLS role, including wrong-tenant reads and writes. SQLite filtering is not RLS evidence.
- [ ] 11. Unauthorized users cannot verify evidence. API RBAC tests exercise this in the development adapter; the database-backed production route remains unwired.
- [ ] 12. Synthetic demo references cannot enter real calculations. Shared domain and FastAPI development-adapter tests enforce this; a production DB calculation path remains unwired.
- [ ] 13. Missing data is surfaced. Shared domain and FastAPI tests cover incomplete evidence; production DB behavior remains unwired.
- [ ] 14. Stale data is visible. Shared domain and FastAPI tests cover stale evidence; production DB behavior remains unwired.
- [ ] 15. Calculation versions are stored durably. The development adapter stores versioned runs in memory; SQLAlchemy persistence is pending.
- [ ] 16. Production smoke test passes. No production deployment of `app/` and `backend/app/` exists.
- [ ] 17. Consent behavior matches policy in production. Tenant/type-scoped consent has API tests in the development adapter; durable DB routes remain pending.
- [ ] 18. Privacy review passes. No recorded review yet.
- [ ] 19. Ethical release checklist passes. No recorded release approval yet.
- [x] 20. Known limitations are documented in [LIMITATIONS.md](LIMITATIONS.md), this gate ledger, and [DEPLOYMENT.md](DEPLOYMENT.md).

Phase A is a foundation under validation. Phase B durable planning, Phase C operational evidence, Phase D context, and Phase E hardening remain incomplete. The frozen `web/` + `api/` + `scripts/service.py` hackathon deployment coexists with the production target `app/` + `backend/app/` + PostgreSQL/PostGIS until the criteria in [DEPLOYMENT.md](DEPLOYMENT.md) are met.
