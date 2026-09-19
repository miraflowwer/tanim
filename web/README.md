# TANIM farmer UI

This is the Step 7 farmer-facing MVP. React displays results from the local
Python service. The browser does not calculate GRCI values.

## Run the integrated MVP

Terminal 1:

```sh
python scripts/service.py --serve
```

Terminal 2:

```sh
cd web
npm ci
npm run dev
```

Open `http://localhost:5173`.

The frontend and backend use committed local files. PSA OpenSTAT is not called
during the live demo.

The form loads crop and region choices from `GET /api/options`. It only shows
crop-region pairs backed by the committed five-year yield summary. The fixed
Tomato and Eggplant buttons use the locked synthetic demo reference. For other
plans, the user must enter a comparison amount, evidence type, geography,
period, and source label. These fields are marked
`user_provided_unverified`. Direct local committed demand is reserved for a
reviewed source integration. TANIM does not invent a demand value.

## Fixed fallback

Set `VITE_USE_MOCK=true` only when you need the two committed fixed demo
screens without the backend. Mock mode does not load the full crop registry and
does not accept arbitrary farmer plans.

## Build

```sh
npm run build
npm run preview
```

Preview also proxies `/api` to the local service.

See [openapi-note.md](openapi-note.md) for the request and response contract.
