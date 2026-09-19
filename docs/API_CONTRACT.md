# Step 7 backend contract

The web app calls the TANIM service at `POST /api/grci`.

The UI does not calculate yield, production, supply load, or risk bands.

## Fixed group demo request

The locked Tomato fixture sends four farmer plans of 10 ha each. Eggplant sends
two farmer plans of 4 ha each.

```json
{
  "plans": [
    {
      "crop": "tomato",
      "region_id": "IV-A",
      "location": "Tanauan, Batangas",
      "farm_size_ha": 10,
      "farm_size_margin_ha": 0,
      "planting_date": "2026-09-01",
      "harvest_period": "2026-12"
    },
    {
      "crop": "tomato",
      "region_id": "IV-A",
      "location": "Tanauan, Batangas",
      "farm_size_ha": 10,
      "farm_size_margin_ha": 0,
      "planting_date": "2026-09-01",
      "harvest_period": "2026-12"
    },
    {
      "crop": "tomato",
      "region_id": "IV-A",
      "location": "Tanauan, Batangas",
      "farm_size_ha": 10,
      "farm_size_margin_ha": 0,
      "planting_date": "2026-09-01",
      "harvest_period": "2026-12"
    },
    {
      "crop": "tomato",
      "region_id": "IV-A",
      "location": "Tanauan, Batangas",
      "farm_size_ha": 10,
      "farm_size_margin_ha": 0,
      "planting_date": "2026-09-01",
      "harvest_period": "2026-12"
    }
  ],
  "use_demo_reference": true
}
```

A request must contain exactly one of `plan` or `plans`. A `plans` list
must not be empty. All plans in one calculation must use the same crop, region,
location, and harvest period.

A non-demo request must send a complete `comparison` object and at least one
non-empty text value in `source_labels`. Non-national comparisons must also
declare a structured `region_id` that matches the farmer plan. If the
geography text itself names a TANIM region, it must agree with that
`region_id`. A manual source label is user-provided traceability, not proof of
review. `local_committed_demand` is reserved for a reviewed source integration,
so a normal request using it is rejected. TANIM does not silently replace
missing real evidence with the synthetic demo baseline.

The temporary low, watch, and high thresholds belong only to the fixed demo.
A normal request does not receive those thresholds automatically. Without a
reviewed `bands` value, a comparable non-demo result stays `unclassified`
even though its supply-load ratio can still be returned.

## Normal request

```json
{
  "plan": {
    "crop": "tomato",
    "region_id": "IV-A",
    "location": "Tanauan, Batangas",
    "farm_size_ha": 2,
    "farm_size_margin_ha": 0.2,
    "planting_date": "2026-09-01",
    "harvest_period": "2026-12"
  },
  "comparison": {
    "amount": 100,
    "unit": "MT",
    "type": "historical_production_baseline",
    "geography": "CALABARZON (IV-A)",
    "period": "2021-2025",
    "region_id": "IV-A"
  },
  "source_labels": ["PSA OpenSTAT table"]
}
```

## Response

The service returns an envelope:

```json
{
  "input": {},
  "lookup": {
    "plan_count": 1
  },
  "result": {},
  "error": null
}
```

For a group request, `input` is the plan list and `lookup.plan_count`
reports how many plans were used.

On failure, `result` is null and `error` contains a code and plain-language
message. The UI displays the error and does not invent a fallback result.

The fixed demo pins the committed DEMO-2026 yield, comparison, source label,
region, and temporary demo bands. A caller cannot override those values through
the demo route. Normal planning uses the committed 2021-2025 PSA regional yield
row and must provide its own traceable comparison. Normal results carry
`evidence_status: user_provided_unverified`; fixed demo results carry
`evidence_status: fixed_synthetic`. Only a trusted reviewed integration may
produce `reviewed_verified` evidence or market-demand wording.

## Planning options

The farmer form loads `GET /api/options`. It returns only planning-supported
crops that also have at least one committed five-year regional yield row. Each
crop lists the regions that are safe to select. The locked demo regions are
identified separately. Manual entry excludes both the synthetic demo type and
`local_committed_demand`. Direct committed demand is reserved for a verified
integration instead of a free-text farmer claim.

## Local endpoint

Run:

```sh
python scripts/service.py --serve
```

The server binds to `127.0.0.1:8000` by default. It serves
`POST /api/grci`, `GET /api/options`, and `GET /api/health`. Vite proxies
`/api` to it in both development and preview mode.

## Hosted endpoints

On Vercel, the same contract is exposed through `api/options.py`, `api/grci.py`, and `api/health.py`. These files reuse `scripts/service.py`; they do not contain a second calculation engine.
