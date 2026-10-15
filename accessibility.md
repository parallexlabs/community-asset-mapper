# Accessibility check record

Local checks performed on 2026-10-11 against the ten-record bundled demonstration
built with `cam build-site --no-tiles`. This record is a report of tested behaviour,
not a statement of accessibility conformance. The sample fields are unverified;
see [DATA.md](../DATA.md).

## Tools and scope

| Tool | Observed version |
| --- | --- |
| Playwright | 1.64.0 |
| axe-core | 4.13.0, read from the scan's `testEngine` |
| axe Playwright integration | 4.13.0 |
| Chromium browser | Google Chrome 156.0.8078.12, headless, macOS |
| Node.js | 22.15.1 |

The development-only [checker](../scripts/check_accessibility.cjs) serves the
output on a loopback HTTP port and aborts external page requests. The check uses
local Leaflet assets and no map tiles. Browser descendants and the local server
were closed after the run. No page errors or failed page requests were recorded.

The checker follows the [Playwright accessibility-testing approach](https://playwright.dev/docs/accessibility-testing).
The browser's native service-type selector was exercised with first-letter
keyboard selection, rather than programmatically setting its value. Keyboard
assertions use the [Playwright keyboard API](https://playwright.dev/docs/api/class-keyboard);
this is not a human assistive-technology review.

## Automated results

The final command exited **0**:

```sh
node scripts/check_accessibility.cjs .release-work/final-site/index.html .release-work/logs/accessibility-pass-results.json
```

Set `CAM_BROWSER_PATH` to the installed browser and install the pinned npm
development dependencies first. For a normal development rebuild, the equivalent
command is `npm run check:accessibility -- dist/index.html`.

| State | Violations | Incomplete rules | Incomplete nodes |
| --- | ---: | ---: | ---: |
| Desktop initial, 1280 x 900 | 0 | 1 | 6 |
| Empty city filter | 0 | 1 | 1 |
| Service popup | 0 | 1 | 6 |
| Narrow viewport, 375 x 812 | 0 | 1 | 18 |

Every incomplete entry belongs to `color-contrast`. Reported reasons include
single-digit marker text, the non-text minus glyph, and elements clipped by the
narrow table's horizontal scroll area. These entries were retained and were not
counted as passes or silently removed. Manual colour-contrast and visual review
remain required before any broader accessibility claim.

## Keyboard results

All **12** recorded behaviour checks passed:

- Skip link moves focus to the service table.
- City filtering updates the table, marker set and announced result count;
  zero-result filtering also works.
- The service-type selector can select the hospital option with keyboard input.
- Map arrow-key panning, plus/minus zoom, and Enter activation of both zoom
  controls work.
- Named markers open details with Enter and Space; Escape or the close control
  closes the popup and returns focus. Focused markers rise above overlapping
  markers.
- Table map actions open service details and permit keyboard exit from the map.
- The CSV download activates with Enter.
- At the narrow viewport, the page has no horizontal overflow and the table
  scroll area responds to Left and Right.
- With JavaScript disabled, all ten table rows and the CSV link remain present.

## Limits and retained evidence

No screen reader, user study, mobile device, forced-colour mode, magnification,
other browser engine, online basemap, or live geocoder was tested. The
JavaScript-disabled check verifies the fallback table and link, not interactive
filters or map actions. [WCAG evaluation guidance](https://www.w3.org/WAI/test-evaluate/)
describes the wider evaluation process that these local checks do not replace.

Raw results and screenshots remain in the excluded `.release-work/logs/`
directory. Earlier checker attempts were retained: native ArrowDown selection
was unreliable in this headless browser, `file:` sandbox stylesheet requests
failed, and one result writer used a package subpath that was not exported.
The final checker uses first-letter selection, local HTTP, and the actual scan
engine version. No generated output or raw browser result is tracked in Git.
