# TANIM farmer UI

This is the Step 7 farmer-facing MVP. React displays results from the Python service. The browser does not calculate GRCI values.

## Run locally

Start the backend from the repository root:

    python scripts/service.py --serve

Then start the web app:

    cd web
    npm ci
    npm run dev

Open `http://localhost:5173`.

The frontend and backend use committed local files. PSA OpenSTAT is not called during the live demo.

The form loads crop and region choices from `GET /api/options`. It only shows crop-region pairs backed by the committed five-year yield summary. The fixed Tomato and Eggplant buttons use the locked synthetic demo reference. Other plans require a comparison amount, evidence type, geography, period, and source label. These fields are marked `user_provided_unverified`.

## Vercel

The repository root contains `vercel.json`. Vercel builds this `web` folder and exposes the same Python service through thin files in `../api/`. See [../docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md).

## Fixed fallback

Set `VITE_USE_MOCK=true` only when you need the two committed fixed demo screens without a backend. Mock mode does not load the full crop registry and does not accept arbitrary farmer plans.

## Build

    npm run build
    npm run preview

Preview proxies `/api` to the local service.

See [../docs/API_CONTRACT.md](../docs/API_CONTRACT.md) for the request and response contract.
