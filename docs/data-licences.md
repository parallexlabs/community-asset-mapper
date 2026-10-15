# Data, reference products, and third-party notices

Licence pages and catalogue metadata were checked on 2026-10-11. This inventory
separates illustrative fixtures from official data products. No source retrieval
receipt authenticates the hospital sample's individual values. Those values are
unverified and must not be used as a current service directory.

## Bundled files

| Files | Status and source | Licence and attribution |
| --- | --- | --- |
| `examples/demo_bc/data/hospitals.csv` | Ten illustrative hospital records associated with [Hospitals in BC](https://catalogue.data.gov.bc.ca/dataset/hospitals-in-bc). Names, addresses and approximate coordinates are unverified against a current source export. Hours and wheelchair-accessibility values are deliberately empty. No provider relationship or endorsement is asserted. | [Open Government Licence - British Columbia, version 2.0](https://www2.gov.bc.ca/gov/content/data/policy-standards/data-policies/open-data/open-government-licence-bc). Catalogue metadata lists this licence. Include the exact notice below. |
| `examples/demo_bc/boundaries/da_sample.geojson`, `csd_sample.geojson` | Synthetic rectangular demonstration polygons. Numeric geography keys are test identifiers; no official geometry or geography correspondence is claimed. Local fixture source: these files and [the fixture inventory](examples/demo_bc/DATA_SOURCES.md). | Apache-2.0, [LICENSE](LICENSE), copyright ParalleX Labs Inc. These fixtures are not Statistics Canada extracts. |
| `examples/demo_bc/population.csv` | Synthetic counts for the demonstration polygons. The date is an illustrative reference label, not an authenticated census observation. Local fixture source: this file. | Apache-2.0, [LICENSE](LICENSE), copyright ParalleX Labs Inc. No Statistics Canada data values are bundled. |
| `fixtures/geocoder/bc_responses.jsonl`, `manifest.yaml` | Synthetic lookup responses using the illustrative hospital addresses and coordinates. No live geocoder capture is claimed. `match_type=fixture`, confidence zero, and fixed reference timestamps make the demonstration explicit and repeatable. | Original fixture structure is Apache-2.0. Associated hospital information retains OGL-BC terms and the exact notice below. |
| `tests/` and dynamically generated test inputs | Constructed test records and workbooks, not accounts, patient records, or service-user data. Local source: the test files. | Apache-2.0, [LICENSE](LICENSE), copyright ParalleX Labs Inc. |
| `schemas/hsds/{address,location,metadata,organization,phone,schedule,service,service_at_location}.json` | Selected HSDS 3.0.1 resource schemas. Each parsed JSON file was compared with its corresponding file under the [publisher's v3.0.1 schema directory](https://github.com/openreferral/specification/tree/v3.0.1/schema) on the check date and matched. | Open Referral, [CC-BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), [publisher licence statement](https://docs.openreferral.org/en/latest/about/license.html). Full text: `schemas/hsds/LICENSE`, copied from the [tagged licence](https://github.com/openreferral/specification/blob/v3.0.1/LICENSE) with line endings and trailing whitespace normalized. No schema-field changes were made. Preserve the exact preferred credit below, source and licence when redistributing. |

### Exact HSDS preferred credit

The [tagged publisher licence](https://github.com/openreferral/specification/blob/v3.0.1/LICENSE)
gives this preferred attribution, reproduced word for word:

> Human Services Data Specification: an Open Referral resource (https://openreferral.org/)

The tagged licence's summary hyperlink points to CC-BY, but its opening statement,
full licence text and [publisher licence page](https://docs.openreferral.org/en/latest/about/license.html)
state CC-BY-SA 4.0. This release retains the upstream licence text and records the
operative ShareAlike licence rather than treating the summary link as a licence change.

### Exact British Columbia notice

The [publisher's licence](https://www2.gov.bc.ca/gov/content/data/policy-standards/data-policies/open-data/open-government-licence-bc)
requires the following fallback attribution when no specific statement is supplied:

> Contains information licensed under the Open Government Licence – British Columbia.

The catalogue includes a separately protected taxonomy definition. That definition
is not reproduced in this project. The sample's extraction date and exact field
correspondence are unverified; the earlier unsupported retrieval-date assertion
has been removed. This inventory does not authenticate third-party data accuracy.

## Referenced products and optional services

### Statistics Canada boundary reference

The [2021 Census boundary product documentation](https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/index-eng.cfm)
is a reference for replacing the synthetic geometry. No official boundary file
is bundled. The earlier census-table claim for synthetic counts has been removed.

The [Statistics Canada Open Licence](https://www.statcan.gc.ca/en/terms-conditions/open-licence)
permits reuse subject to its terms. Its source acknowledgement templates are,
word for word:

> Source: Statistics Canada, name of product, reference date. Reproduced and distributed on an "as is" basis with the permission of Statistics Canada.

For a value-added product:

> Adapted from Statistics Canada, name of product, reference date. This does not constitute an endorsement by Statistics Canada of this product.

Replace `name of product` and `reference date` with the actual product and date
when official information is introduced. Neither notice is used to mislabel the
synthetic fixtures as Statistics Canada information.

### British Columbia Address Geocoder

The live provider is optional and is not used by the demo or tests. Its
[publisher API terms](https://www2.gov.bc.ca/gov/content/data/policy-standards/data-policies/open-data/api-terms-of-use-for-ogl-information)
refer information reuse and attribution to OGL-BC. Use the British Columbia
notice above for licensed responses, retain provenance, and review the current
terms before live use. This release check made no live geocoder request.

### OpenStreetMap basemap

The default site configuration references OpenStreetMap tiles. No tiles or OSM
data extracts are bundled. [OpenStreetMap's copyright page](https://www.openstreetmap.org/copyright)
identifies the Open Database Licence and gives the contributor credit:

> © OpenStreetMap contributors

The site displays that credit with a link when tiles are enabled. Follow the
[standard tile usage policy](https://operations.osmfoundation.org/policies/tiles/)
when using the optional online basemap. `--no-tiles` keeps the marker map active
without contacting a tile server.

## Bundled map library

`src/community_asset_mapper/site/assets/leaflet.min.js` and `leaflet.css` identify
Leaflet 1.9.4. Its [tagged BSD-2-Clause licence](https://github.com/Leaflet/Leaflet/blob/v1.9.4/LICENSE)
is reproduced verbatim in `assets/LEAFLET_LICENSE.txt` and copied into generated
sites. Required copyright-holder names are legal notices, not directory users.
The Apache-2.0 code licence does not replace the upstream schema, library or data
licences. Dependency packages retain their own licences; the npm checker is a
development dependency and is not copied into a generated site.
