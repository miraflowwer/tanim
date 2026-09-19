# TANIM implementation ownership

Default ownership minimizes merge conflicts. Cross-owner edits should be small and coordinated.

| Member | Primary ownership |
|---|---|
| Member 1 | shared frontend shell/navigation/responsive primitives, auth/onboarding UI, Farmer features |
| Member 2 | Coordinator, Reviewer, Admin, maps/charts/context, notifications/search/history |
| Member 3 | backend, PostgreSQL/PostGIS, OpenAPI, ingestion, security/operations, release |

## Member 1

Preferred paths:

```text
app/src/app/**
app/src/components/layout/**
app/src/components/forms/**
app/src/components/feedback/**
app/src/features/auth/**
app/src/features/onboarding/**
app/src/features/farms/**
app/src/features/plans/**
app/src/features/crops/**
```

Member 1 owns root frontend integration points. Other members should extend role/feature modules instead of repeatedly editing root files.

## Member 2

Preferred paths:

```text
app/src/features/coordination/**
app/src/features/evidence/**
app/src/features/organization/**
app/src/features/context/**
app/src/features/data-health/**
app/src/features/notifications/**
app/src/features/search/**
app/src/components/charts/**
app/src/components/map/**
```

## Member 3

Preferred paths:

```text
backend/**
openapi/**
backend/alembic/**
docs/implementation/TRACEABILITY_STATUS.md
production deployment/security configuration
```

## Shared-file rule

Avoid simultaneous broad edits to:

```text
app/src/App.tsx
app/src/styles.css
app/src/lib/api.ts
app/src/types.ts
```

The bootstrap introduces route modules so ordinary role-navigation work no longer requires editing the same constants in `App.tsx`.

If a member needs another owner's file:

1. add the exact request to `BLOCKERS.md`;
2. prefer the file owner to make the shared change;
3. if the requester must make it, keep the commit narrow and notify the owner before both branches diverge.
