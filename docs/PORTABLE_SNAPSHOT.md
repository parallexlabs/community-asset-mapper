# Portable snapshot export

This component exports normalized working records from the community asset mapper into a self-contained offline SQLite snapshot plus a JSON receipt. It is a narrow handover format, not production hosting, compliance certification, source authentication, geocoding, HSDS conformance, or client delivery.

## Scope

The exporter accepts a JSON list of InternalRecord-like objects. Each object must contain `organization`, `service`, `location`, and may contain `source_row`. Unknown top-level keys are rejected.

Entity key whitelists match the original pydantic models. Extra keys on any entity are rejected. Fields outside the projection are accepted only to document what is omitted; they do not appear in SQLite or in the logical digest.

### Projected fields

| Entity | Stored | Ignored (accepted in input, not stored) |
|--------|--------|-------------------------------------------|
| organization | id, name, provenance columns | description, email, website, alternate_name |
| location | id, organization_id, name, location_type, latitude, longitude | address, geocode |
| service | id, organization_id, location_id, name, service_type, last_verified, hours, wheelchair_accessible | description, url, extra |
| source_row | none | entire object ignored |

Ignored metadata may be arbitrary valid JSON subject to size caps. It is not logged and does not affect the digest.

## Input limits

- JSON file at most 10 MiB
- At most 10,000 records
- At most 10,000 characters per retained string
- The API also caps compact ASCII-escaped JSON at 10 MiB, including ignored fields
- All input strings and keys are capped; UTF-8-invalid strings are rejected
- Nesting at most 64 levels, at most 200,000 JSON values including keys
- Integers anywhere in the input must fit signed 64-bit; these are tool limits, not domain rules
- Non-finite JSON numeric tokens and non-finite Python floats rejected
- Duplicate JSON object keys rejected
- Empty list is valid

The Python API accepts plain JSON-compatible built-in objects only. Custom mappings, classes, and cyclic structures are rejected predictably without invoking user-defined properties.

## Validation rules

Required id and name fields must be non-empty strings with no leading or trailing whitespace and no embedded NUL. Strings are preserved verbatim; there is no Unicode or date normalization.

Optional metadata strings may be null, including missing provenance fields. Booleans must be true, false, or null exactly (not 1 or 0). Dates such as `last_verified` are opaque strings or null; no ISO or freshness validation is applied.

Latitude and longitude must both be numeric or both null. Coordinates must be finite with latitude in [-90, 90] and longitude in [-180, 180]. Integer and float are allowed; bool is not. Zero is stored as 0.0.

Per record, organization ids on organization, service, and location must match. Service `location_id` must be null or exactly equal to the record location id.

Entities are merged by id across all input rows. Identical projected fields collapse. Any projected-field conflict rejects the export, even when conflicting rows are not adjacent. Differences in ignored fields alone do not change the logical digest.

Rows are sorted by entity id before digest and insert.

## SQLite layout

Fixed DDL with primary keys NOT NULL, organization foreign keys on locations and services, and a composite foreign key on services `(location_id, organization_id)` referencing locations `(id, organization_id)` so a service cannot reference another organization's location when foreign keys are enforced.

`wheelchair_accessible` is stored as INTEGER NULL, 0, or 1 with a CHECK constraint.

Writes use parameterized inserts and fixed table name constants only. Before commit, `PRAGMA foreign_keys=ON` is verified, then `foreign_key_check` and `integrity_check` run. After close, the file is reopened read-only via a quoted file URI and counts, joins, null or bool storage and all selected row values are checked against the input projection. This is structural self-checking, not source authentication.

## Logical digest

The digest is SHA-256 of deterministic UTF-8 JSON containing schema, version, and sorted normalized table rows using `sort_keys=True`, `separators=(',', ':')`, `ensure_ascii=True`, and `allow_nan=False`.

The digest is stable under input row order and JSON key order changes. Identical projected data with different ignored fields yields the same digest. This component does not claim byte-identical SQLite files across platforms or runs.

## Receipt

`receipt.json` is written last, after the database is closed and read-only structural checks succeed. Consumers must parse the complete receipt, not merely test its filename's existence: a crash during JSON writing may leave a truncated marker. The two files are not jointly crash-atomic or guaranteed power-loss durable.

Receipt fields:

- `schema`, `version`, `logical_digest`
- `input_records`, `organizations`, `locations`, `services`
- `located_services`, `unlocated_services`
- `metadata_status`: `declared_not_authenticated`
- `source_validated`: false
- `privacy_certified`: false
- `external_action_authorized`: false
- `post_write_structure_verified`: true
- `software`, `software_version` (descriptive labels, not authenticated software fingerprints)

The receipt never copies caller-supplied raw input or private ignored fields. No freshness timestamp is generated.

## Directory publish contract

POSIX rename can replace an empty directory, so this exporter does not claim an exclusive atomic two-file directory publish via check plus rename.

Safer narrow contract:

1. Validate all input before touching the output path.
2. Reject an output path that already exists, including empty directories, files, or symlinks.
3. Reject symlink components in the lexical output path and its parent chain before resolution, and reject `..` traversal.
4. Require an existing trusted local parent directory.
5. Atomically reserve the final directory with `mkdir(exist_ok=False)` and mode `0700`.
6. Create `snapshot.sqlite` exclusively inside the new directory.
7. Write `receipt.json` exclusively last.

On failure after reservation, the incomplete new directory is left intact for operator inspection. The exporter never deletes the output directory, input files, or unrelated user files. Incomplete directories cannot be retried or overwritten at the same path; operator-approved cleanup or a new output path is required.

This assumes a trusted stable parent and no hostile concurrent parent mutator. It is not a filesystem security certification.

## CLI

```
python scripts/export_portable_snapshot.py INPUT_JSON OUTPUT_DIR
```

Success prints the receipt JSON to stdout and exits 0. Controlled errors print `export failed` to stderr without echoing input values and exit 2.

The CLI reads only regular input files, rejects a final-component symlink and reads at most the byte cap plus one before parsing. Parent-directory changes, concurrent input mutation and malicious SQLite/process state are outside the trusted local filesystem contract. This Unix-oriented file-open guard is tested on macOS, not Windows. Do not use restricted/private inputs merely because the projection omits some fields.

## Python API

```python
from export_portable_snapshot import export_snapshot

receipt = export_snapshot(records, output_directory)
```

Returns the receipt dict and writes `snapshot.sqlite` and `receipt.json` under `output_directory`.

## Explicit non-goals

- No arbitrary SQL or URL access
- No application dependencies beyond the Python standard library in this script
- No integration promise with the legacy CSV exporter (which maps falsy latitude to empty string; this component preserves 0.0)
- No performance benchmarks or privacy certificates

## Reference documentation

The implementation and tests in this repository are the evidence for the local
contract above. Standard-library behaviours referenced by that contract are
documented in [sqlite3](https://docs.python.org/3/library/sqlite3.html),
[JSON](https://docs.python.org/3/library/json.html), and
[filesystem operations](https://docs.python.org/3/library/os.html).
No public deployment, external source authentication or performance result is
asserted by this component description.
