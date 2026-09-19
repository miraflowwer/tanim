# TANIM frontend feature modules

New final-product work should be feature-local so three members can work in parallel without repeatedly editing the same root files.

Preferred structure:

```text
features/<feature>/
  <feature>.routes.tsx
  <feature>.api.ts
  <feature>.types.ts
  <feature>.views.tsx
  components/
```

Not every feature needs every file. Keep modules as small as the actual workflow requires.

## Ownership

- Member 1: auth, onboarding, farms, plans, Farmer-facing crops/profile/consent
- Member 2: coordination, evidence, organization/admin, context/data-health, notifications, search
- Member 3: no default frontend feature ownership; backend/API contracts live under `backend/` and `openapi/`

## Contract rule

When a feature needs a missing API, record it in `docs/implementation/API_REQUESTS.md`. A typed temporary fixture may unblock rendering, but it must not be presented as a real production success path.
