# TANIM farmer UI (Step 7 MVP)

Vite + React mock-first interface. Displays precomputed GRCI results only —
no GRCI math lives in JavaScript.

## Run

```sh
cd web
npm install
npm run dev      # http://localhost:5173, mock data ON
npm run build    # production bundle for pitch laptop
npm run preview  # serve the bundle locally
```

Live backend:

```sh
# web/.env.local
VITE_USE_MOCK=false
VITE_API_BASE_URL=http://localhost:8000
```

`vite.config.js` also proxies relative `/api` → `:8000` in dev, so the app
code never hardcodes a host.

## Switch to Member 1's backend

Single function: `src/api/grciClient.js → fetchGrci(planInput)`.
`src/config.js → USE_MOCK` flips mock vs `POST /api/grci`.
Request/response contract: `openapi-note.md`.
Mock shape: `src/mocks/grciMocks.js` (mirrors `compute_grci()` keys).

## Demo (3 minutes)

1. Click **Tomato demo (high)** → 40 ha → 600 MT vs 375 synthetic → high.
2. Click **Eggplant demo (low)** → 8 ha → 96 MT vs 180 synthetic → low.
3. Click **Baseline wording** / **National context** → guards hold.
4. Fill the form with 2 ha ± 0.2 → estimated-range path.

## Guards

Historical production is never called market demand. National figures are
context only. Synthetic demo is always badged. See `DESIGN.md`.
