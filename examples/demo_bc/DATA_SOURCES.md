# Demonstration fixture inventory

Read [DATA.md](../../DATA.md) for the complete licence inventory, publisher URLs,
and exact attribution notices checked on 2026-10-11.

| Local sample | Source and licence | Interpretation |
| --- | --- | --- |
| `data/hospitals.csv` | [Hospitals in BC](https://catalogue.data.gov.bc.ca/dataset/hospitals-in-bc), [OGL-BC 2.0](https://www2.gov.bc.ca/gov/content/data/policy-standards/data-policies/open-data/open-government-licence-bc) | Ten illustrative records. Individual fields and the extraction date are unverified. Hours and wheelchair-accessibility assertions are empty. |
| `boundaries/da_sample.geojson`, `boundaries/csd_sample.geojson` | Local synthetic fixture source, Apache-2.0, [LICENSE](../../LICENSE) | Demonstration rectangles, not official census boundaries. |
| `population.csv` | Local synthetic fixture source, Apache-2.0, [LICENSE](../../LICENSE) | Invented demonstration counts, explicitly labelled synthetic. |
| `../../fixtures/geocoder/manifest.yaml`, `bc_responses.jsonl` | Local synthetic fixture source, Apache-2.0 for fixture structure; associated hospital information retains [OGL-BC](https://www2.gov.bc.ca/gov/content/data/policy-standards/data-policies/open-data/open-government-licence-bc) | Lookup fixtures, not captured API results. Confidence zero and timestamps are demonstration constants. |

Contains information licensed under the Open Government Licence – British Columbia.

The [2021 Census boundary product](https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/index-eng.cfm)
is a reference only. Neither geometry nor population values here are official
Statistics Canada observations. The demo quality-report date is fixed for
reproducibility and is not the time a check was executed.
