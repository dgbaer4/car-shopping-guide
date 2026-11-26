# CSG-I09 Pilot UAT interface corrections

## Changes

- **UAT-001** uses seven local, generated WebP images for body-style choices. The repository history across available branches contained no reusable vehicle photos. Each image uses a white vehicle, the same front three-quarter perspective, and neutral studio lighting and background. The visible body-style names and descriptions remain the button labels. Empty image alt text avoids repeating that information.
- **UAT-002** aligns numeric inputs at the bottom of each assumptions row, allowing the labels above them to wrap independently.
- **UAT-003** displays purchase price, sales tax, one-time fees, and cash needed at purchase by default. Each card has its own disclosure button for annual energy and operating costs, resale value, cash expenditure, and net ownership cost. Opening or closing the disclosure keeps the estimate and input state intact.

## Verification

| Check | Result |
| --- | --- |
| `node --test tests/*.test.mjs` | All 8 test files passed. |
| `python -m unittest discover -s tests -p 'test_*.py'` | All 46 tests passed. |
| Integration catalog regeneration | All 1,406 configurations regenerated and the result matched the tracked catalog byte for byte. |
| `python tools/build_pilot_release.py --site /tmp/csg-uat-site` | The pilot catalog validated and the release package included all seven WebPs. |
| Playwright with Chromium 156, packaged site | Passed at 390 × 844 and 844 × 390 for phones, 768 × 1024 and 1024 × 768 for tablets, and 1280 × 900 for desktop. |

The browser checks used the Walnut Creek saved-profile fixture. They verified local image decoding, accessible selection by mouse and keyboard, persisted selection after reload, and same-origin requests. The assumptions grid had one column on the portrait phone and three at the other tested sizes, with aligned input tops even when captions wrapped and no horizontal page overflow. Checks also covered the four default rows on all five initial cards, keyboard expansion, accessible disclosure state, independence across two cards, and the ten-card expansion path. A $21,500 quote with 10% tax and $500 in fees yielded $24,150 at purchase. Closing and reopening the financial details preserved the computed amounts, the quote, and an unapplied fee edit. Applying the edit to $750 updated the purchase estimate to $24,400.

## File ownership for integration

The UAT branch owns the body-style imagery and assumptions CSS in `index.html`, disclosure markup in `engine/browser-results.mjs`, the WebP assets, and their entries in the release asset allowlist in `tools/build_pilot_release.py`. The pricing work owns calculators, pricing inputs and data, and recommendation behavior. As of verification, no published pricing branch or PR was available for comparison. If pricing changes the shared renderer or release allowlist, merge those files by section and rerun the packaged browser checks.


## CSG-I11 defect register · 2026-11-26

| Defect | Integrated correction | Status |
| --- | --- | --- |
| UAT-001 | Seven local vehicle images, with accessible body-style names and selection | Verified in packaged Chromium |
| UAT-002 | Aligned numeric inputs with wrapping labels across phone, tablet and desktop | Verified in packaged Chromium |
| UAT-003 | Independent financial details preserve quotes, calculation state and unapplied assumptions | Verified in packaged Chromium |
| UAT-004 | Sourced ranges, condition/date/basis disclosure and quote overrides replace the budget-derived price default | Verified in packaged Chromium |

The complete commuter scenario passed at five viewport sizes, including tablet portrait and landscape. The default five retain suitable unpriced vehicles. The optional priced view supports like-for-like cash comparisons where evidence exists. All four corrections await final physical iPad/Safari acceptance. [Integration report](integration-report-v0.3.md) · [Pricing coverage and limitations](vehicle-pricing-v1.md)
