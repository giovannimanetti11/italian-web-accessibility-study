# Pilot 500: validation and protocol decisions (9 October 2026)

## Dataset and independent integrity verification

Pilot run: `runs/pilot-500-iwss-46XZX`, collected using **draft v0.1.0**.
Frame: fixed Tranco standard list 46XZX (8 July 2026), exactly 10,022 .it domains.
Pilot: simple random sample without replacement, seed 20261007, n=500.
Sample CSV SHA256: `8a204f76c9f039c9dd6b5142e73bb6ba4179fc26bcf04683b20bbf888cf3b1bd`.

- 500 input targets, 500 unique result files, 500 byte-identical worker/merged files.
- 369 completed domains; 131 domain-level failures.
- 1,750 selected page slots; 1,697 successfully evaluated; 53 page-level failures.
- 5,503 page/rule violation occurrences and 42,220 affected nodes.
- 355/369 completed sites showed at least one automatically detected violation (96.21%).
- Excluding redirects to another registrable domain: 333/347 (95.97%).
- 22 cross-registrable-domain redirects.
- 500 CSV manifest rows? No: **1,750 selected page rows**, independently verified
  against the 1,750 exported JSONL rows and per-domain manifests.
- **None of these observations establishes WCAG conformance or non-conformance.**
- 131/500 missing evaluations prevent naive extrapolation of the observed 96.21%
  to the original full frame. No invented imputation or missing-at-random assumption.

## Failure review and recoverability

Original failure classes:

| Class | Count |
|---|---:|
| HTTP 403 | 58 |
| Apex DNS unresolved or non-public address | 33 |
| Browser navigation interrupted | 15 |
| Certificate errors | 9 |
| Navigation timeout | 8 |
| Connection refused | 4 |
| Other HTTP homepage status | 2 |
| Other browser failure | 2 |
| **Total** | **131** |

The separate conservative HTTP diagnostic did not follow redirects or bypass 403s.
The 58 HTTP 403 targets were deliberately not re-probed. DNS-level verification
found 14 of the 33 DNS-failed apex names had globally routable `www` DNS.
Eight had an HTTPS response (200, 301 or 302) on `www`.

Independent Chromium targeted rescan of those eight original apex target names,
using a safe `www` fallback, initially returned **7 scanner-complete / 1 HTTP 400**;
26 page selections, 22 page evaluations *under the draft completeness logic*.
Further independent content review showed one HTTP-200 homepage was actually
`Request Rejected` (`iss.it`, 9 DOM elements) and another was marked complete
without any successfully evaluated page (`promotorifinecobank.it`). Thus only
**five of eight** are currently supported as actual evaluable sites. Both false
success patterns are now guarded explicitly in v1.0. The raw pilot records are
unchanged; the validation is stored separately under `runs/validation-www-8`.

No TLS verification was disabled. Other failures may reflect temporary network
conditions, server behavior, blocking or actual unavailability; they are never
scored as accessibility passes or violations.

## Missing-data pattern by original rank quartile

| Quartile | Complete | Failed | Completion |
|---|---:|---:|---:|
| Q1 | 86 | 39 | 68.8% |
| Q2 | 88 | 37 | 70.4% |
| Q3 | 89 | 36 | 71.2% |
| Q4 | 106 | 19 | 84.8% |

The completed-only subsample does **not** have uniform evaluation success
across quartiles. Missingness is a primary outcome and must be reported in
the study. Rankings are based on positions in this 500-domain sample, not
economic sectors or measured traffic.

## Manifest assessment

- 100 URL rows across 20 stratified sites were reviewed for **URL-level semantic
  plausibility**; this is not a manual evaluation of rendered page content.
- Targeted issues observed: a serialized CMS `?query=[...]` filter incorrectly
  classified as a functional page; a generic /policy/notice-at-collection path
  selected as a deep page; some account/module links or voting URLs deserve
  attention in any deeper rendered-content audit.
- `iper.it/accessibilita` can be a legitimate accessibility notice, but is not
  necessarily representative of the site's main customer flows.
- Several .it sites selected English-language pages; the study frame is
  **.it domains**, not exclusively Italian-language content.
- Among the 70 sites completed in both the 100 and 500 pilots, 18 had changed
  URL manifests. Some changed due to earlier sampler fixes; others reflect
  live rotating articles, products, redirects, or session/challenge URLs.
  A deterministic algorithm does not make external web content temporally immutable.
- Improvements adopted for the **next** protocol: exclude exact generic
  /policy/ segments, avoid structured JSON CMS query filters as functional search,
  and use HTTPS/HTTP `www` fallbacks only on original apex names after failure.
  Explicit HTTP 4xx responses remain terminal. No changes to draft v0.1 raw data.

## Scope, methods and disclosure

This is a **large-scale automated barrier detection study**, not a WCAG-EM
conformance assessment. The W3C's WCAG Evaluation Methodology 2.0 (Group Note,
23 July 2026, https://www.w3.org/TR/wcag-em-2/) informs scope and representative
sampling, but actual conformance evaluation requires additional expert/manual
tests beyond these axe-core results.

Primary outcomes to report separately:

1. Domain-level evaluation completion, failure taxonomy, redirects.
2. Among completed original .it sites, percentage with >=1 automatically
   detected A/AA issue; report redirected-site sensitivity separately.
3. Frequencies of page/rule violations and affected nodes, not conflating
   sites, pages, rules and DOM nodes.
4. WCAG 2.0/2.1 and additional 2.2 signals broken out by rule tags.
5. Page-slot success/failure and impact-class distributions.
6. Explicit desktop viewport; mobile can be a separately designed follow-up.
7. Retained errors and anomalies, not silently replaced by retries.

The final cohort must be **rescanned in its entirety** under one frozen v1.0
protocol, without incorporating any v0.1 pilot records.

## Safety decision

The host's Chromium cannot activate its native user-namespace sandbox under
existing AppArmor restrictions. Before launching the full run, isolate the
scanner in a limited Docker container with no sensitive host mounts, unprivileged
browser execution, private/link-local network egress denial, and resource caps.
Do not alter the host's global firewall or AppArmor rules. Verify these guards
with an actual network test. Freeze v1.0 and launch the final collection only
after the isolation validation succeeds.
