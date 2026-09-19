# Limitations

- The selected PSA OpenSTAT plant tables contain millions of source cells. The repository stores an audited manifest and deterministic materializer instead of pretending a small static CSV is the complete corpus.
- PSA tables can be revised. Run the fetcher with `--verify-only` before a new materialization.
- Historical farmgate and retail prices exist in overlapping PSA series with changing commodity specifications and geographic codes. Keep series_id. Do not join or overwrite values only by crop name and year.
- Cross-source crop names are not always identical. TANIM only auto-joins exact normalized labels. Similar labels stay separate until they have a safe mapping.
- Farmgate legacy coverage is 1990 to 2020, with legacy cutflowers starting in 2006. The current farmgate series is 2010 to 2026.
- Retail legacy coverage is 1990 to 2021, the revised series is 2012 to 2021, and the current series is 2018 to 2026.
- Detailed crops production and area tables exposed through OpenSTAT begin in 2010. PSA states that older annual 1990 to 2009 data remain available from the Crops Statistics Division, but they are not exposed in the linked OpenSTAT tables.
- Farmgate and retail source rows can be blank when a commodity was not observed in a place or period. TANIM must keep those values missing.
- Some crop-production tables do not publish NCR. TANIM must not invent an NCR production value.
- DA weekly price monitoring is NCR-only. It is not a substitute for Luzon-wide price coverage.
- Supply Utilization Accounts are national. They are national utilization context, not a Luzon demand estimate. GRCI must label them as national utilization context, never as Luzon demand.
- Verified Luzon-local market demand is not available for every crop. GRCI callers must select the reference tier that matches the evidence: local committed demand, local historical absorption, national utilization context, or historical production baseline.
- Historical production is a coordination baseline only. It must never be labelled as market demand.
- A farmer-entered farm size can be approximate. GRCI calculations should carry an area range using the stated margin instead of treating the estimate as exact.
- TANIM does not set a default real-world farm-size margin yet. A default needs pilot evidence. The fixed synthetic demo uses a zero margin only to keep the demo reproducible.
- PAGASA outlook statements can change with later advisories.
- Open-Meteo values are requested at runtime.
- NCCAG remains a reference to the official map. Raw GIS layers are not redistributed here.
