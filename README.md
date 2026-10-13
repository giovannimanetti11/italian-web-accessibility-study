# Italian Web Accessibility Study (IWASS)

[![Code: MIT](https://img.shields.io/badge/code-MIT-blue.svg)](LICENSE)
[![Data: CC BY 4.0](https://img.shields.io/badge/data-CC%20BY%204.0-lightgrey.svg)](LICENSE-DATA)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](pyproject.toml)

IWASS measures accessibility problems that can be detected automatically on popular Italian websites. The completed October 2026 study covers **10,022 `.it` domains** and **34,641 successfully evaluated pages**, using Chromium, Playwright and axe-core.

**Paper:** Giovanni Manetti, *Italian Web Accessibility 2026: An Observational Analysis of 10,022 Domains and 34,641 Web Pages*. PerseoDesign Research. DOI: [10.5281/zenodo.23347092](https://doi.org/10.5281/zenodo.23347092).

**Dataset:** *Italian Web Accessibility Study (IWASS): Automated WCAG Barrier Measurement Dataset for 10,022 Italian Domains*. DOI reserved: [10.5281/zenodo.23346985](https://doi.org/10.5281/zenodo.23346985). The public dataset deposit is separate from this source repository; check the Zenodo record for its publication status.

---

## What this is

This repository contains the acquisition pipeline, fixed sampling rules, tests and methodological record for the Italian Web Accessibility Study. It does not contain an automated WCAG compliance certification service.

The population is the full `.it` slice of the [Tranco](https://tranco-list.eu/) top-one-million list **46XZX**, dated **8 July 2026**. It is a popularity-ranked frame, not a random sample of all Italian websites. The exact 10,022-domain input frame is also used by the [Italian Web Security Study (IWSS)](https://github.com/giovannimanetti11/italian-web-security-study). This makes matched-domain comparisons possible without conflating security measurements with accessibility measurements.

Each domain is approached through its homepage. Up to four additional pages are selected using fixed functional, content, deep-path and seeded rules. Candidate URLs come from the rendered homepage and the site's sitemaps; the scanner does not recursively crawl the entire site. axe-core then evaluates the selected pages against automatically testable WCAG A/AA rules.

The **unit of sampling is the original `.it` domain**, including when its homepage redirects elsewhere. Results from redirected sites are identified as such.

## Findings

| Measurement | Result |
|---|---:|
| Domains in the frame | 10,022 |
| Domains with an evaluable result | 7,573 (75.6%) |
| Domains without an evaluable result | 2,449 (24.4%) |
| Sampled-page records from evaluable domains | 36,038 |
| Successfully evaluated pages | 34,641 |
| Evaluable domains with at least one detected violation | 7,328 (96.8%) |
| Violation-rule occurrences | 106,815 |
| DOM nodes affected by those occurrences | 890,680 |

Among evaluable domains, the most widespread findings were **insufficient colour contrast** (6,129 domains), **links lacking accessible names** (4,894), **insufficient target size** (3,080) and **image alternatives** (3,016). At least one automated violation was found in more than 96% of evaluable domains in each Tranco popularity quartile.

**A detected axe-core violation is not a complete WCAG conformance determination.** Similarly, a page with no detected violation is not necessarily accessible. The study cannot assess every interaction, page state or assistive-technology use case.

The 2,449 non-evaluable domains are retained as errors rather than counted as accessible or inaccessible. Of these, 1,150 returned HTTP 403. They are a substantial source of potential selection bias, and the results should not be reported as representing the accessibility of all Italian websites.

Full interpretation, sensitivity checks and limitations are in the [paper](https://doi.org/10.5281/zenodo.23347092).

## Measurement design

The frozen **protocol v1.0.0**, developed after 20-, 100- and 500-domain pilots, specifies:

- Maximum of five pages per domain: homepage, functional, content, deepest observed and deterministic seeded selection, with defined fallbacks.
- Candidate URLs discovered only from homepage anchors and sitemaps, with exclusions for legal boilerplate, downloads and state-changing paths.
- Playwright with pinned Chromium **153.0.8010.12**; JavaScript enabled; **1366 × 768** viewport; `it-IT` locale; `Europe/Rome` time zone; fixed **1.5-second** post-navigation wait.
- axe-core **4.14.0**, restricted to the WCAG 2.0/2.1/2.2 A and AA tags.
- Independent browser context per domain, no login, form submission, cookie-banner interaction or access-control bypass.
- No connections to non-public network addresses. Full collection runs inside a restricted, unprivileged Docker environment.

See [protocol/methodology.md](protocol/methodology.md) for the sampling algorithm, pilot findings, limitations, exact environment and documented operational hotfixes. Version 1.0.0 refers to the **study protocol**, not the number of Docker image rebuilds used to finish the collection.

## Pipeline

```text
Tranco 46XZX (July 2026)  ->  exact .it cohort (10,022)
                                      |
                                      v
                          two isolated scanner workers
                                      |
                        Chromium / Playwright rendering
                                      |
                      deterministic page selection (<= 5)
                                      |
                         axe-core WCAG A/AA checks
                                      |
                   atomic per-domain results + resume
                                      |
                   page export, URL manifest, QA report
                                      |
                     published derived dataset (Zenodo)
```

Two independent workers process deterministic, non-overlapping shards. Per-domain JSON files are written atomically and are not replaced when a failed process resumes. A bounded watchdog restarts workers that stop producing results; restarts and Docker image changes are recorded. Study outcomes and operational failures are intentionally kept distinct.

## Repository structure

```text
iwass/       scanner, URL discovery, page sampling, axe integration, storage
scripts/     scan CLI, parallel runner, dataset export, validation and diagnostics
infra/       pinned Docker image and restricted container entrypoint
protocol/    frozen methodology and pilot validation records
tests/       sampler, scanner, URL safety, recovery and reporting regressions
data/input/  local input files (not distributed here)
runs/        per-run outputs (not distributed here)
dataset/     public dataset schema and release notes
```

The source repository does **not** include the original rank/domain list, unredacted URL manifests, site titles, raw page results or DOM selectors. The source of the domain frame is public, but the study follows the IWSS practice of keeping original identifiers out of the GitHub archive. A separately deposited dataset uses **unsalted SHA-256 domain identifiers**, compatible with IWSS. Those identifiers are pseudonymized, **not anonymous**: dictionary matching of public domain names is possible.

## Reproduce the study

Requires Python **3.13**, [uv](https://docs.astral.sh/uv/), Node.js/npm and Docker with the ability to apply the container's network restrictions.

```bash
git clone https://github.com/giovannimanetti11/italian-web-accessibility-study.git
cd italian-web-accessibility-study
uv sync --frozen --dev
npm ci
uv run pytest
uv run ruff check .
```

### Prepare the original domain frame

Download the archived [Tranco list 46XZX](https://tranco-list.eu/download/46XZX/1000000) and extract its CSV. Build the exact `.it` input without changing ranks:

```bash
uv run python scripts/prepare_tranco_frame.py \
  /path/to/tranco-46XZX-full.csv \
  data/input/iwss-tranco-it-2026-07-08.csv
```

The preparation script verifies **10,022 domains** and the original frame SHA-256:

```text
6d57a4bdf1fecc941b5218d88c7b5d5b9980e876f7f5abdb98d4fdbc6db25471
```

A different checksum means the list, filtering or byte serialization differs from the original study. Do not use such a file for a claimed exact replication.

### Run a collection

For a full run, use the **isolated Docker setup**. The host browser was not an acceptable sandbox for untrusted site JavaScript during the original collection.

```bash
docker build -f infra/Dockerfile -t iwass-scanner:1.0.3 .
bash scripts/start_final_study.sh
```

The launcher is configured for the original study ID and fixed input path; edit the launcher or run ID **before** starting a genuinely new study. Do not overwrite or combine old results. The container enforces two low-priority workers, 2 CPU cores, 6 GiB of RAM, a read-only filesystem, blocked private-network egress and a bounded restart policy.

When a run finishes, the parallel runner builds `accessibility-results.jsonl`, `url-manifest.csv`, `quality-report.json` and a summary. The original run completed on **13 October 2026**. For reproducibility use the recorded environment and note that live sites may have changed since collection.

## Data

The dataset's Zenodo DOI is **[10.5281/zenodo.23346985](https://doi.org/10.5281/zenodo.23346985)**. This repository intentionally keeps raw collection results out of version control. See [dataset/README.md](dataset/README.md) for the public table structure, key construction and release status.

The dataset and paper have **separate DOIs**. The data are intended for independent reanalysis and, using the same domain hash, future comparison with the [IWSS dataset](https://doi.org/10.5281/zenodo.21323346). No combined security/accessibility outcome is claimed by this study.

**Release status:** the complete run is archived and the Zenodo dataset record is being prepared. An 88-row stratified manual review and one page-manifest anomaly still require final disposition; these items are described in the study report and must not be concealed at publication. Check the Zenodo record for the released dataset version and availability.

## Methodology and ethics

The scanner only visits public webpages through normal browser navigation; it does not authenticate, submit forms, attempt exploitation or bypass anti-bot controls. Only publicly available destinations are evaluated. Addresses in private and link-local networks are blocked within the isolated runtime.

The protocol follows principles in [WCAG-EM](https://www.w3.org/TR/WCAG-EM/) but is **not** itself a complete WCAG-EM evaluation. Automated WCAG checks, by definition, cannot substitute for manual accessibility testing. Full site conformance and usability with assistive technologies are outside the claims of this work.

Study domain errors and cross-domain redirects are disclosed rather than excluded silently; see the frozen [methodology](protocol/methodology.md).

## Citation

For the scientific findings, cite the paper:

> Manetti, G. (2026). *Italian Web Accessibility 2026: An Observational Analysis of 10,022 Domains and 34,641 Web Pages*. PerseoDesign Research. https://doi.org/10.5281/zenodo.23347092

For a secondary analysis of the dataset, cite its own DOI once the dataset is published:

> Manetti, G. (2026). *Italian Web Accessibility Study (IWASS): Automated WCAG Barrier Measurement Dataset for 10,022 Italian Domains*. https://doi.org/10.5281/zenodo.23346985

Machine-readable citation metadata are in [CITATION.cff](CITATION.cff).

## License and contact

- **Code:** [MIT](LICENSE).
- **Public dataset and exported research tables:** [CC BY 4.0](LICENSE-DATA).
- **Contact:** Giovanni Manetti — giovanni@perseodesign.com
