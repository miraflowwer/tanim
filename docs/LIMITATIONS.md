# Limitations

- The selected PSA OpenSTAT plant tables contain millions of source cells. The repository stores an audited manifest and deterministic materializer instead of a small sample that could be mistaken for the full source.
- PSA tables can be revised. Run the live verification before a new materialization.
- Farmgate and retail prices use overlapping official series with changing commodity descriptions and geographic codes. TANIM keeps each source version separate.
- Cross-source crop names are not always identical. TANIM only auto-joins exact normalized labels. Similar labels stay separate until a safe mapping is reviewed.
- Detailed crop production and area tables exposed through OpenSTAT begin in 2010. Older rows mentioned by PSA are not invented or silently reconstructed.
- Source rows can be blank when a commodity was not observed in a place or period. TANIM keeps those values missing.
- Some crop-production tables do not publish NCR. TANIM does not invent an NCR value.
- DA weekly price monitoring in the repository is NCR-only. It is recent context, not complete Luzon price coverage.
- PSA Supply Utilization Accounts are national. TANIM treats them as national utilization context only and never as Luzon or local demand.
- Verified Luzon-local committed demand is not available for every crop. The GRCI result must show the exact reference type and its evidence note.
- Local historical sold or accepted volume is an absorption proxy. It is not the same as current or committed market demand.
- Historical production is a past-supply baseline. It can support a baseline comparison, but it must not be labelled as market demand.
- The fixed demo comparison values are synthetic. They are not observed local market demand.
- Farm size can be approximate. GRCI calculations carry the stated area margin instead of treating every estimate as exact.
- TANIM does not set a default real-world farm-size margin yet. A default needs pilot evidence.
- PAGASA outlook statements can change with later advisories.
- Open-Meteo values are requested at runtime.
- NCCAG remains a reference to the official map. Raw GIS layers are not redistributed in this repository.
