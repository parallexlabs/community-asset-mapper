# Contributing

Use constructed test records and cite the publisher, licence and exact attribution
notice for any new data. Keep credentials, personal data, internal notes and
local output out of changes. Follow the typed module boundaries and existing
formatting. Check the [data inventory](DATA.md) and [security scope](SECURITY.md).

## Local setup

Use the wheel acquisition and offline installation commands in [README.md](README.md).
Keep the environment fresh when validating a release. The pinned requirements
are a development replay snapshot, not a claim of compatibility with every
future dependency version. [pip download](https://pip.pypa.io/en/stable/cli/pip_download/)
can prepare a platform-specific wheelhouse before disconnecting the checks.

```sh
export PATH="$PWD/.venv/bin:$PATH"
export CAM_OFFLINE=1
export PYTHONPATH="$PWD/scripts/offline"
ruff check
mypy src
pyright
pytest --cov
cam run-demo
cam build-site -o dist --no-tiles
```

The offline hook denies Python connection and name-resolution audit events.
The test fixtures also block socket connection APIs. Live providers are mocked;
no accounts or keys are needed. This is a check of fixture behaviour, not live
provider connectivity or a system-wide firewall. See
[Python audit hooks](https://docs.python.org/3/library/sys.html#sys.addaudithook).

## Browser checks

The root npm packages are development-only. Acquire them from the registry with
`npm ci --ignore-scripts`, then use a locally installed Chromium browser:

```sh
npm run check:accessibility -- dist/index.html .cam/accessibility/results.json
```

Set `CAM_BROWSER_PATH` before running the command. The checker records automated
axe results separately from keyboard assertions and verifies its browser process
cleanup. It serves local files through a loopback HTTP port and aborts external page requests. The tooling does
not establish accessibility conformance; read [the tested scope](docs/accessibility.md)
and [Playwright's accessibility guidance](https://playwright.dev/docs/accessibility-testing).

## Issues and changes

Provide versions, a minimal command and constructed input when reporting a bug.
Do not include private raw records or credentials in logs. Security reporting is
covered by [SECURITY.md](SECURITY.md). Publication and release dates are maintainer
decisions; local passing checks are not evidence of a hosted CI run or deployment.
