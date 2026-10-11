# Local release checks

Checked on 2026-10-11 with Python 3.12.12 on macOS. This is local release
preparation; no hosted CI run, public release, deployment or provider operation
is asserted. External source and licence facts are in [DATA.md](../DATA.md).

## Installation and checks

A new environment without system site packages was populated from a local
wheelhouse. Acquisition from PyPI preceded offline checks. The pinned
[requirements](../requirements-dev.txt) include the editable-build helper.
The initial editable install started before dependencies completed and failed;
a later attempt exposed that missing helper. Both logs were retained, the helper
was pinned, and the final editable install exited 0. The clean-clone procedure
below installs the complete pinned set in one step.

The local environment used Ruff 0.17.0, mypy 2.4.0, Pyright 1.1.414,
pytest 9.1.1 and coverage 7.16.2. [pip's wheelhouse documentation](https://pip.pypa.io/en/stable/cli/pip_download/)
explains the acquisition and offline-install mechanism.

```sh
python3.12 -m venv .venv-release
.venv-release/bin/python -m pip install --no-index --find-links .release-work/wheelhouse -r requirements-dev.txt
.venv-release/bin/python -m pip install --no-index --no-build-isolation --no-deps -e .
export PATH="$PWD/.venv-release/bin:$PATH"
export CAM_OFFLINE=1
export PYTHONPATH="$PWD/scripts/offline"
export TMPDIR="$PWD/.release-work/tmp"
```

| Check | Exit code and result |
| --- | --- |
| `ruff check` | 0 |
| `mypy src` | 0, no issues in 36 source files |
| `pyright` | 0, no errors, warnings or information messages |
| `pytest --cov --basetemp=.release-work/pytest-final --cov-report=json:.release-work/logs/coverage-final.json` | 0, 118 tests and two subtests passed; 90.58% combined line/branch coverage, above the configured 90% floor |
| `cam run-demo` | 0, ten records, selected schema checks valid, zero duplicate groups, 30 quality issues, four synthetic geography metrics |
| `cam build-site -o dist --no-tiles` | 0 |
| `python -m build --wheel --no-isolation --outdir .release-work/wheels` | 0; required package data, schema and site assets present |
| Citation and workflow metadata checks | Citation passed the [CFF 1.2.0 schema](https://citation-file-format.github.io/1.2.0/schema.json); workflow YAML parsed with read-only repository permission and six steps |

Python connection and name-resolution audit events were denied during checks,
and the test fixtures block socket connection APIs. These controls are local
fixture checks, not a system-wide firewall. See [Python audit-hook documentation](https://docs.python.org/3/library/sys.html#sys.addaudithook).
No live geocoder or tile request was made. Accessibility results, versions,
incomplete findings and tested keyboard behaviour are in [accessibility.md](accessibility.md).

## Replay procedure

The required final-commit replay uses a fresh local clone inside the excluded
work directory. It installs a new environment from the complete pinned
wheelhouse, runs the same checks, and compares SHA-256 values for every file in
`.cam/demo/` and the separately built `dist/` site. The demo has 18 files and the
site has six files. Each relative filename must exist on both sides and its bytes
must match; no timestamp stripping or result normalization is used.

```sh
git clone --no-hardlinks . .release-work/checkout-final
cd .release-work/checkout-final
python3.12 -m venv .venv
.venv/bin/python -m pip install --no-index --find-links ../wheelhouse -r requirements-dev.txt
.venv/bin/python -m pip install --no-index --no-build-isolation --no-deps -e .
export PATH="$PWD/.venv/bin:$PATH"
export CAM_OFFLINE=1
export PYTHONPATH="$PWD/scripts/offline"
ruff check
mypy src
pyright
mkdir -p .cam
pytest --cov --basetemp=.cam/pytest-replay
cam run-demo
cam build-site -o dist --no-tiles
```

Keep temporary directories inside the repository when executing this procedure.
The exact final commit, command exit codes and checksum comparison receipt are
recorded in the maintainer's local review report after this documentation is
committed. Inserting the final commit identifier into this file would change
the commit being checked. No claim of a remote CI execution is made here.

The earlier installed-wheel replay, performed outside the source directory,
matched all 18 demo files and six site files. Its evidence was retained before a
subsequent table-scroll and marker-focus improvement; the final replay checks the
updated candidate. The [CI workflow](../.github/workflows/ci.yml) acquires wheels,
then installs offline and runs fixture checks and a packaged-wheel demo. Only
Python 3.12 on macOS has been executed locally; the Linux runner remains untested.

## Content review

The tracked-file scan checks secret signatures, absolute home paths, known local
identity strings, prohibited attribution names and em dashes. Email candidates
were limited to reserved `example.com` examples, and credential assignments were
mock values in provider tests. Required upstream legal credits are retained;
public institutional directory names are not represented as clients. No personal
service-user or patient records are bundled. This is a content review of the
candidate, not a guarantee about arbitrary future imports.

The internal instructions, research, project brief and work products are excluded
through local `.git/info/exclude`. Demo output, environments and browser artifacts
remain local and untracked. The commit-message hook is a byte-identical copy of
the prescribed local hook. There is no publication, push or GitHub repository-creation
receipt in this release preparation.
