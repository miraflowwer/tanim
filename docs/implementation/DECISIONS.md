# TANIM implementation decisions

Record only decisions that affect more than one member or materially change an implementation contract.

## D-001 — Use one integration branch

- Status: Accepted
- Decision: Use `feat/final-product-integration` as the shared integration target. Member branches start from the same bootstrap commit.
- Reason: Feature branches can progress independently while `main` remains stable.

## D-002 — Feature-local frontend modules

- Status: Accepted
- Decision: New frontend work should prefer `app/src/features/<feature>/` with feature-local route, API, type, and view modules.
- Reason: The current P0 frontend concentrates routes and calls in shared files that would otherwise create avoidable merge conflicts.

## D-003 — Server remains authoritative

- Status: Accepted
- Decision: GRCI calculation, evidence eligibility, role authorization, and tenant isolation remain server-owned.
- Reason: Parallel frontend work must not create temporary business-logic forks that become permanent.

## D-004 — Member 2 narrow shared-file changes

- Status: Accepted
- Decision: Member 2 extends `Role` with coordinator/admin, maps backend roles in `fetchMyRole`, adds `global.ts` navigation plus reviewer/admin/coordinator entries through the sanctioned stubs, registers `cplan`/`ref`/`history` detail routes, and renders the new screens from one `App.tsx` block. Network stays in `*.api.ts`; views never call `fetch`.
- Reason: Role-aware operations UI needs the shared role union and route table. All other Member 2 work stays inside `features/` and `components/charts|map`.
