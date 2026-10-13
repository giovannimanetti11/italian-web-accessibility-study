# IWASS methodology - frozen protocol v1.0 (9 October 2026)

## Purpose

Measure the prevalence and distribution of automatically detectable accessibility
barriers on a reproducible sample of pages from Italian `.it` websites.

The automated scanner does **not** determine WCAG conformance. It records only
findings that axe-core can automatically classify as violations, while preserving
`incomplete` results separately for methodological analysis.

## Sampling frame

The final sampling frame is the exact `.it` slice used by IWSS, recovered from
Tranco standard list `46XZX` dated 2026-07-08. It contains 10,022 domains and
has SHA-256
`6d57a4bdf1fecc941b5218d88c7b5d5b9980e876f7f5abdb98d4fdbc6db25471`.
This byte-for-byte match allows matched-domain security/accessibility analyses
against the IWSS frame.

A sampled unit is the original `.it` registrable domain, even when it redirects
to another public registrable domain. Cross-domain redirects are recorded and
must be reported separately in analysis; a sensitivity analysis may exclude them
from prevalence estimates to avoid measuring an unrelated destination site.

## Page sampling

Maximum five pages per sampled domain.

1. `homepage`: final rendered homepage after redirects.
2. `functional`: deterministic hash-ranked URL matching functional hints
   (contact, search, booking, login, cart, quote, etc.).
3. `content`: deterministic hash-ranked URL matching content hints
   (service, about, article, product, news, etc.).
4. `deep`: URL at the greatest observed path depth, with deterministic
   hash-ranking among ties.
5. `seeded`: deterministic hash-ranked URL from the remaining pool.

Category hints are never matched as raw substrings. Functional hints must match
an entire path segment or the beginning of a normalized segment (for example,
`/contact`, `/contact-us`, `/prenota-online`); `cart` must not match `Cartier`,
`cartuccia` or `Cartosio`, and `contatti` inside a product slug is not functional.
Low-value boilerplate URLs such as cookie/privacy policies, legal notices,
terms, sitemaps and feeds are excluded from representative-page sampling.
State-changing/action-like paths such as compare/add, wishlist/add, add-to-cart
and logout are also excluded. Common non-HTML media/document extensions are
filtered before page selection.

If a category is unavailable, remaining slots are filled by deterministic
hash-ranking. Candidate URLs come only from:

- anchors present in the JavaScript-rendered homepage;
- URLs in sitemap files discovered at conventional paths or through robots.txt.

There is no unrestricted recursive crawl in protocol v1.0.

## Rendering environment

- Chromium through Playwright.
- JavaScript enabled.
- Fresh browser context per domain.
- Fixed viewport: 1366 x 768.
- Default User-Agent of the pinned Chromium build, recorded in every run.
- Locale: it-IT.
- Time zone: Europe/Rome.
- Fixed post-DOMContentLoaded wait: 1500 ms.
- No cookie-banner interaction.
- No form submission, login or state-changing action.
- Non-public network destinations are blocked.

The exact Chromium, Python and axe-core versions are written into each result.

## Accessibility evaluation

axe-core is injected as an init script and run after rendering.

Run-only tags:

- wcag2a
- wcag2aa
- wcag21a
- wcag21aa
- wcag22a
- wcag22aa

The primary scientific outcome is **automatically detected WCAG A/AA barriers**,
not "WCAG compliance".

For each page the scanner stores:

- requested and final URL;
- sample-selection reason;
- HTTP status;
- rendering time;
- DOM SHA-256;
- DOM node count;
- title and document language;
- axe-core violations;
- axe-core incomplete results;
- pass and inapplicable counts;
- tool/environment versions and actual Chromium User-Agent.

Raw HTML is not stored.

## Reproducibility

Each run records:

- protocol version;
- input file reference;
- page cap;
- WCAG tags;
- browser/tool versions;
- run timestamps.

The page manifest is exported independently from accessibility results. A later
rerun can therefore evaluate the exact frozen URL manifest even if discovery has
changed. Protocol changes after the pilot must increment the protocol version.

## Pilot sequence

1. Development smoke tests on non-study domains.
2. 20-domain technical pilot.
3. 100-domain sampling/reliability pilot and sampler corrections.
4. 500-domain validation using the stabilized sampler, before the protocol freeze (completed).
5. Stratified manifest review, error taxonomy, redirect analysis and execution profiling.
6. Freeze protocol v1.0 after validating the 500-domain pilot (completed).
7. Final 10,022-domain run.

The final cohort is collected under v1.0 only; v0.1 pilot results are not merged into it.

## Pilot-500 execution specification

- Input: deterministic 500-domain random sample from the exact IWSS .it frame.
- Tranco list ID: 46XZX, dated 2026-07-08; seed: 20261007.
- Input CSV SHA-256: 8a204f76c9f039c9dd6b5142e73bb6ba4179fc26bcf04683b20bbf888cf3b1bd.
- The 500-domain sample contains all 100 domains from the previous pilot.
- Two separate scanner processes on HomeServer; deterministic round-robin
  assignment of 250 ranked domains per worker.
- Per-worker Chromium instances use independent browser contexts per domain.
- Run ID: pilot-500-iwss-46XZX; raw outputs remain under runs/.
- Automated axe findings are not proof of WCAG compliance or noncompliance.
- Primary results remain exploratory until the protocol is frozen and the
  final cohort has been collected under protocol v1.0.

## Frozen v1.0 changes from the pilot

Protocol freeze date: **2026-10-09**. Rationale and validation evidence:
`protocol/pilot-500-validation.md`. This is a fresh dataset collection; it
**must never mix** draft v0.1.0 pilot records with v1.0 records.

- Original apex HTTPS then HTTP navigation; only after failed navigation, attempt
  conventional HTTPS/HTTP `www` for apex hostnames. **HTTP 4xx is terminal** and
  no anti-bot protection, certificate verification or access controls are bypassed.
  All redirects are recorded, including those to another registrable domain.
- Exclude legal notices under generic `/policy/` routes and structured CMS
  `?query=[...]` URLs from the functional-search classification.
- The original domain remains the statistical sampling unit, whether its homepage
  resolves to an apex, a `www` host or another registrable domain.
- Record failed domains as immutable attempts; interruption recovery must
  skip completed *and failed* domain files rather than silently rescan errors.
  Controlled retries, if needed, go into separate validation runs.
- Reject recognizable soft-block/challenge HTML responses even when HTTP reports
  success (e.g. `Request Rejected`); a domain with no successfully evaluated
  sampled pages is **not** counted as completed. Unknown bot challenges remain
  a stated source of residual false positives and require sensitivity review.
- Exactly two scanner workers on HomeServer, configured with low CPU priority
  and Docker CPU/memory/process limits.
- The browser and all page JavaScript execute in a disposable Docker container
  with frozen code/axe assets baked into the container image, read-only input
  data mounts, only the runs directory writable, Linux capabilities dropped
  before Chromium starts, no new privileges and explicit
  private/link-local egress deny rules. HomeServer's global firewall unchanged.
- Pinned dependencies: `uv.lock`, `package-lock.json`, axe-core 4.14.0,
  Python 3.13.14 and Playwright 1.63.0 (Chromium 153.0.8010.12).
- Site load and sampling behavior otherwise unchanged: maximum 5 pages,
  1366x768 desktop viewport, fixed locale/timezone and timing, and the
  deterministic sitemap/homepage candidate algorithm.

The study follows representative sampling principles discussed in the
W3C WCAG-EM 2.0 Group Note (https://www.w3.org/TR/wcag-em-2/) **but is not**
a WCAG-EM conformance evaluation: no expert/manual assessment of all WCAG
criteria, keyboard interactions, assistive technology operation or workflows
is claimed. Report all automated findings with their limitations.

On completion of the final cohort, independently verify every run record and
the two worker exports; stratify missingness by rank, and report cross-domain
redirect sensitivity. The user-facing publication and FIAS import require
separate quality review after final data collection.


## Operational stability hotfix — 10 October 2026

The study's v1.0 sampling and automated accessibility evaluation methodology
remains unchanged. During the full run, a malformed double-dot hostname in a
third-party resource request raised `UnicodeEncodeError` inside
`socket.getaddrinfo()`. The Playwright route listener then failed, and the
`BrowserContext.close()` code surfaced a secondary
`Route.continue_: function takes exactly 5 arguments` TypeError. Worker 01
stopped while worker 02 continued; persisted results remained intact.

The patch release (`iwass-scanner:1.0.1`) fails closed for invalid IDNA and
malformed URL hostnames; catches request-disappearance errors in route handling;
and unregisters outstanding routes before context teardown. This does not
relax private-network protections, alter WCAG tags, page-selection priorities,
browser version or result schemas.

Existing per-domain outputs are **not overwritten** on resume. For
reproducibility, report the two container image digests and the timestamp/domain
count of the patched-run restart alongside the final dataset. The regression
test invokes the actual previously failing malformed IDNA input; tests also
cover malformed IPv6 URLs, route failures and context teardown.


## Operational stability hotfix — 11 October 2026

After the 10 October fix, the study container stopped at roughly 39% when
both Playwright workers encountered `BrowserContext.unroute_all: Target crashed`.
The v1.0.2 **operational** patch guards context cleanup, restarts disconnected
Chromium without changing the browser build, recycles it every 100 domains and
allows a bounded, logged worker restart for process-level failures.
An unrecoverable browser launch is an infrastructure failure rather than a
domain accessibility result. All pre-existing domain files remain immutable;
the collection uses the same Tranco frame, page cap, WCAG tags and sampler.
The image change and exact resume checkpoint are tracked in the run's
maintenance-events audit log. These changes are disclosed for reproducibility.


## Worker no-progress watchdog — 12 October 2026

The pinned v1.0 study stalled with 7,915 recorded domains after an internal
Playwright Node.js assertion left both worker processes alive but producing no
new result files for over 17 hours. Process-exit monitoring alone did not
detect this failure. Patch 1.0.3 introduces a 600-second per-worker
no-result watchdog, checked every 30 seconds. It terminates only the
stalled worker's dedicated process group (including browser processes), first
with SIGTERM and then with SIGKILL if needed, and relaunches the worker
under the existing eight-restart maximum. A restart is logged with reason,
attempt, last persisted count, and PID in worker-restarts.jsonl. A process
which keeps failing after the bound exits nonzero; it is not silently
interpreted as thousands of inaccessible domains.

The watchdog does not change any sampling, browser, WCAG, or analytical
criteria. A domain interrupted mid-scan is retried because its final
atomic JSON record was never produced. Previously recorded success and
error domains are never reprocessed. Image and resume details are captured
in the run's maintenance-events.jsonl log.
