# TANIM production frontend (Phase A)

`app/` is the React + TypeScript frontend for the production direction in `TANIM_Production_PRD_Ethics.md`. `backend/app/` owns calculation, evidence eligibility, authorization, and the versioned API. `web/`, `api/`, and `scripts/service.py` remain the deployed hackathon path until the production path passes the release gates in `docs/20-gates.md`.

## Development runtime

From a fresh checkout, install `backend/requirements.txt` and `app/package-lock.json`. Run the API in explicit development mode and run Vite in a second terminal:

```sh
TANIM_RUNTIME_MODE=inmemory ALLOW_DEV_AUTH=true python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
npm --prefix app ci
npm --prefix app run dev
```

Vite proxies `/api/v1` to port 8000. Visit the Vite URL, open Profile, and use the labeled development sign-in. The API's seeded users and organization are for development only. A production PostgreSQL configuration currently fails closed because the route repository adapter is not wired; see `docs/LIMITATIONS.md`.

`npm --prefix app run build` typechecks and builds the app. `npm --prefix app test` checks committed contract artifacts and the bundle budget after a build. `npm --prefix playwright test -- --project=mobile --project=desktop` runs real browser and axe tests against the built app and development API.

## Evidence and offline display

New plans and revisions require a successful FastAPI response. The browser serializes API requests and renders returned calculations; it does not compute GRCI, decide evidence eligibility, or assign a trusted coordination status. The exact seeded Tomato plan can show a committed, labeled synthetic result snapshot while the API is unavailable. Other new plans retain their form draft and show a service error. The fixed offline overview is labeled synthetic and never used as a production aggregate. No live PSA, DA, PAGASA, or weather request is required for the seeded demo.

The development API is an in-memory adapter. It is not durable and does not establish production tenant isolation. The production PostgreSQL/PostGIS schema, migrations, and RLS mechanism have separate tests and remain a target until routes use the database adapter.
