# Security

This is a local demonstration release. There is no supported hosted service or
published security-response commitment. Before publication, the maintainer must
provide a private vulnerability-reporting contact through the project's release
channel. Do not put private input records, credentials or exploit payloads in a
public issue. Report reproducible steps with constructed test data and versions.

Use trusted local input and output directories. CSV and Excel reads have byte
limits; the XML workbook parser does not execute macros. YAML uses a safe loader.
See [PyYAML guidance](https://pyyaml.org/wiki/PyYAMLDocumentation) and
[openpyxl loading options](https://openpyxl.readthedocs.io/en/stable/api/openpyxl.reader.excel.html).
These controls do not establish privacy compliance or protect against every
malicious file. Workbooks, JSON state and output can contain supplied values.

The demo and tests use fixtures. A live geocoder sends addresses to an external
service; review its [API terms](https://www2.gov.bc.ca/gov/content/data/policy-standards/data-policies/open-data/api-terms-of-use-for-ogl-information)
and obtain authority for the input before use. Never put a credential in input
fixtures, output or logs. Live-provider errors are reported without echoing
addresses, URLs or provider exception text.

Generated HTML uses template escaping and popup text nodes. The table and CSV
exports contain directory fields. Formula-leading text cells are neutralized,
but an export is not a personal-data filter. Review data before publication.
See [OWASP CSV injection guidance](https://owasp.org/www-community/attacks/CSV_Injection).
Tile attribution HTML is trusted operator configuration, not an input-data field.

The portable SQLite component's separate trusted-filesystem contract and limits
are in [its documentation](docs/PORTABLE_SNAPSHOT.md). Keep incomplete exports for
inspection and use a new destination after failure. No production threat model,
penetration test, data authentication or compliance certification is claimed.
