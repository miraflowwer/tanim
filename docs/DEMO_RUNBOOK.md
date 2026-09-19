# TANIM demo runbook

This runbook uses the integrated Step 7 MVP. The browser talks only to the
local Python service. PSA OpenSTAT is not needed during the live demo.

## Before the demo

Install the web packages before the event:

```sh
cd web
npm ci
npm test
npm run build
```

Run all local checks from the repository root:

```sh
python tests/test_datasets.py
python tests/test_crop_registry.py
python tests/test_yield_reference.py
python tests/test_grci.py
python tests/test_service.py
python tests/test_mvp_e2e.py
```

## Start the MVP

Terminal 1:

```sh
python scripts/service.py --serve
```

Terminal 2:

```sh
cd web
npm run dev
```

Open `http://localhost:5173`.

After setup, the demo can run with the internet disconnected. Both parts use
committed local files.

## Tomato fixed demo

1. Click Tomato demo (high).
2. TANIM sends four 10 ha farmer plans to the local service with the
   synthetic DEMO-2026 reference selected on purpose.
3. Expect planned area: 40 ha.
4. Expect synthetic reference yield: 15 MT/ha.
5. Expect expected production: 600 MT.
6. Expect synthetic comparison reference: 375 MT.
7. Expect supply load: 1.6.
8. Expect Demo risk state: high.
9. Point to the evidence badge and note. They say the reference is synthetic
   and not observed market demand.

## Eggplant fixed demo

1. Click Eggplant demo (low).
2. TANIM sends two 4 ha farmer plans.
3. Expect planned area: 8 ha.
4. Expect synthetic reference yield: 12 MT/ha.
5. Expect expected production: 96 MT.
6. Expect synthetic comparison reference: 180 MT.
7. Expect supply load: about 0.53.
8. Expect Demo risk state: low.

## Farmer form

The form also accepts a farm-size margin. The page labels a range as an
estimated range.

The crop and region menus come from the local `GET /api/options` endpoint.
Only crop-region pairs with a committed five-year yield row are selectable.

The fixed Tomato and Eggplant buttons are separate from the normal form.
Manual entry offers historical production baseline, local historical
absorption, and national utilization context. It does not offer DEMO-2026 or
`local_committed_demand`.

For one normal check, enter a 2 ha Tomato plan for Tanauan, harvest `2026-12`,
then enter 100 MT, `historical_production_baseline`, `CALABARZON (IV-A)`,
`2021-2025`, and a source label such as `PSA OpenSTAT table`. The response
should use the committed PSA yield, return expected production, and mark the
comparison `evidence_status: user_provided_unverified`. It must not allow
market-demand wording. The source label is only a traceability label; TANIM
does not treat it as independent review.

Non-national comparisons also carry the selected region ID. TANIM returns an
error instead of filling missing evidence with the demo value. A direct local
committed-demand value is accepted only by a future reviewed source
integration, not by this free-text form.

## Safe failure cases

- Unknown crop: no crop is guessed.
- Missing regional yield in a normal request: no yield is guessed.
- Missing comparison in a normal request: no synthetic demand is substituted.
- Direct committed demand from a manual request: the request is rejected as
  unverified evidence.
- Invalid area or date: the request is rejected.
- National utilization: context only. It does not produce a local demand risk.

## Backup plan

If the UI fails, run:

```sh
python scripts/service.py --demo
```

The JSON output keeps the fixed Tomato result: 40 ha, 600 MT, 1.6, Demo risk state high.

If the backend cannot be started, set `VITE_USE_MOCK=true` and restart the
web app. Mock fallback supports only the two fixed synthetic fixtures. It does
not accept arbitrary farmer plans.

## Browser smoke pass (record once per release head)

Real browser check, not covered by `tests/test_mvp_e2e.py` (backend HTTP +
source-string checks only):

- [ ] Tomato demo in real browser shows `Demo risk state: high`, 40 ha, 600 MT.
- [ ] Eggplant demo in real browser shows `Demo risk state: low`, 8 ha, 96 MT.
- [ ] One normal form (2 ha Tomato, Tanauan, harvest `2026-12`, 100 MT
  `historical_production_baseline`) shows baseline/unclassified, never
  `GRCI risk state`, and marks `user_provided_unverified`.

Record: date, head SHA, browser, pass/fail. Example: `2026-09-19, <SHA>,
Chrome/Edge desktop, 3/3 pass`.
