# TANIM deployment

TANIM keeps one repository root for data, Python logic, tests, and the React interface.

## Vercel layout

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

## Release check

Before a release, run all Python tests and the frontend test and build commands. After Vercel deploys, open `/`, `/api/health`, then run the Tomato and Eggplant demo buttons.
