# Pilot 100 - exact IWSS Tranco frame (46XZX)

Date: 2026-10-07
Protocol: draft v0.1, pre-freeze
Purpose: validate the scanner and sampler on a deterministic random sample from the exact 10,022-domain IWSS security-study frame.

## Sampling frame

The original IWSS frame was recovered exactly from Tranco standard list `46XZX`, dated 2026-07-08.

- Tranco list ID: `46XZX`
- Tranco date: 2026-07-08
- `.it` rows: 10,022
- filtered frame SHA-256:
  `6d57a4bdf1fecc941b5218d88c7b5d5b9980e876f7f5abdb98d4fdbc6db25471`
- match against IWSS manifest: exact, byte-for-byte

Pilot selection:

- method: random without replacement
- seed: `20261007`
- n: 100
- pilot CSV SHA-256:
  `1e1e67fa5d4367db075c04aac61c9da761bf1e252b9b23b8f015ee76b1ad34a5`

The selection was regenerated twice and compared byte-for-byte; it is deterministic.

## Rank coverage

The 100 sampled domains cover the full Tranco rank range of the recovered frame.

- minimum rank: 5,110
- Q1: 196,383.75
- median: 538,244
- Q3: 773,897.75
- maximum rank: 994,815

The sample is not concentrated in the head of the list.

## Domain-level outcome

100 domains were processed.

- 70 complete
- 30 domain-level errors
- completion rate: 70.0%

Error taxonomy:

- 14 unresolved/non-public destinations rejected by the network guard
- 8 HTTP 403 homepages
- 8 browser/navigation failures

The navigation group includes timeouts, connection refusal, certificate-name errors and
browser error-page interruptions.

## Page-level outcome

Across the 70 completed domains:

- 327 page slots selected
- 312 pages successfully evaluated
- 15 selected URLs returned an error/non-success status
- page success rate: 95.4%

HTTP status among successful page navigations was overwhelmingly 200.

Sampled-page counts by completed domain:

- 63 domains: 5 pages
- 3 domains: 2 pages
- 3 domains: 1 page
- 1 domain: 3 pages

Selection reasons:

- homepage: 70
- functional: 49
- content: 55
- deep: 67
- seeded: 64
- fallback: 22

## Discovery size

Per completed domain:

- median candidate URLs: 242
- p95 candidate URLs: 5,300
- maximum candidate URLs: 6,660
- median sitemap URLs: 178
- p95 sitemap URLs: 5,000
- maximum sitemap URLs: 5,000
- median rendered-homepage links: 54
- p95 rendered-homepage links: 355
- maximum rendered-homepage links: 1,707

The existing deterministic caps therefore activate on some large sites.

## Timing

Per completed domain:

### Homepage load

- median: 2,439 ms
- p90: 3,411 ms
- p95: 3,906 ms
- max: 6,301 ms
- mean: 2,611 ms

### Sitemap discovery

- median: 1,243 ms
- p90: 8,746 ms
- p95: 20,390 ms
- max: 43,891 ms
- mean: 4,036 ms

### Total discovery

- median: 1,565 ms
- p90: 8,800 ms
- p95: 20,802 ms
- max: 43,951 ms
- mean: 4,283 ms

### Total domain scan

- median: 20,684 ms
- p90: 44,670 ms
- p95: 57,549 ms
- max: 77,068 ms
- mean: 24,267 ms

Sitemap discovery is a real tail-latency contributor but is not the dominant cost for the
median domain.

## Sitemap-budget decision

No global wall-clock budget is introduced at this stage.

Reason: a time budget depends on transient network conditions and can change the sampled
URL set between otherwise identical runs, which weakens reproducibility.

The current deterministic limits remain:

- max sitemap files: 8
- max sitemap URLs: 5,000
- per-request timeout: 12 seconds

Performance should be improved later through controlled concurrency and/or deterministic
discovery limits, not by silently changing the sample according to network timing.

## Cross-domain redirects

Three completed domains redirected to a different registrable domain:

- `trivenet.it` -> `planetel.it`
- `ayrion.it` -> `ced.it`
- `hotmail.it` -> `microsoft.com`

These remain in the raw dataset with `redirected_cross_domain=true`.

Primary reporting must disclose these cases and a sensitivity analysis should exclude them
when estimating accessibility characteristics of the original sampled domain population.

## Sampler review and regressions

Manual review of the 100-domain manifest exposed additional draft-sampler issues.

### False functional matches

Observed:

- article slug beginning with `carrello-`
- sports promo path `quote-maggiorate`

Fix:

- exact functional segments are accepted;
- only a small set of route-like prefixes may match short normalized segments;
- search detection through query strings is based on query keys, not arbitrary values.

Real-world targeted rescans confirmed:

- `ilgerme.it` now selects `/contatti`
- `sportbet.it` now selects `/supporto/contatti`

### Boilerplate plural variant

`cookies_policy` was not filtered by the singular cookie rules.

Fix: plural cookie/cookies variants are covered.

`agestanet.it` no longer samples the cookie-policy URL in the targeted regression.

### Action-like URLs

A product comparison `.../product_compare/add/...` URL appeared in the sample.

Fix: action-like paths such as compare/add, wishlist/add, add-to-cart and logout are
excluded from representative sampling.

The targeted `plexishop.it` rescan instead selected normal product/content pages.

### Media extension

A `.jpe` image was selected as a deep page on `ilgerme.it`.

Fix: additional media extensions including `.jpe`, `.avif`, `.bmp`, TIFF and common
video formats are excluded.

The final `ilgerme.it` regression selected an HTML category page as deep.

## Final regression state

After the pilot-derived sampler corrections:

- static checks pass;
- 13/13 unit/regression tests pass;
- targeted real-world rescans pass for the identified edge cases.

The full 100-domain run is retained as a pilot artifact; its accessibility counts are
exploratory because the sampler was refined after manifest review.

## Exploratory accessibility output

These figures validate the pipeline only. They are not final prevalence estimates.

Across the original 70 completed domains / 312 successfully evaluated pages:

- 66 of 70 completed domains had at least one automated axe violation;
- 1,031 page-rule violation occurrences;
- 6,202 affected nodes;
- impacts: 672 serious, 302 critical, 57 moderate.

Most frequent page-rule occurrences:

- `color-contrast`: 205
- `link-name`: 161
- `image-alt`: 101
- `target-size`: 73
- `button-name`: 70
- `meta-viewport`: 57
- `label-content-name-mismatch`: 51

No claim of WCAG conformance/non-conformance is made from these automated results.

## Decision after pilot 100

Retain:

- exact 10,022-domain IWSS frame;
- deterministic random sampling for pilots;
- maximum five pages per domain;
- rendered-homepage + sitemap discovery;
- deterministic representative-page sampling;
- separate violations/incomplete results;
- cross-domain redirect flag;
- current sitemap caps;
- per-domain timing instrumentation;
- resumable atomic output.

Before protocol v1.0 / final-scale collection:

1. run a 500-domain validation using the stabilized sampler;
2. review a stratified subset of manifests from that run;
3. quantify cross-domain redirects and failure taxonomy again;
4. choose controlled concurrency for the final 10,022-domain run and record it as part of the execution environment;
5. freeze protocol v1.0 before interpreting final results.
