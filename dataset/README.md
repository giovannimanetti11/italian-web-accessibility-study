# IWAS dataset

The public dataset is deposited separately from this codebase on Zenodo.

- **Dataset DOI (reserved):** https://doi.org/10.5281/zenodo.23346985
- **Paper DOI (reserved):** https://doi.org/10.5281/zenodo.23347092
- **Source frame:** Tranco list 46XZX (2026-07-08), entire .it slice of 10,022 domains
- **Collection:** 9–13 October 2026
- **Protocol:** 1.0.0
- **Data license:** CC BY 4.0

The candidate export is structured as follows:

| File | Unit |
| --- | --- |
| domains.csv | One row for each original sample domain (including errors) |
| pages.csv | One row per sampled page of evaluable domains |
| violations.csv | One row per automated axe-core violation rule occurrence |
| incomplete.csv | Checks requiring further review; not confirmed violations |
| quality-summary-public.json | Descriptive integrity and quality counts |
| dataset-summary.json | Verified counts |
| protocol-methodology.md | Frozen acquisition and operational history |
| README.txt, LICENSE.txt, SHA256SUMS.txt | Documentation, rights and checksums |

**The ZIP and tabular observations are not included in this source release.**
This is deliberate: the independent 88-row stratified review and the identified
sampling anomaly require final disposition before the deposited data can be
described as validated. Files in exports/ will be published only as part of
a separately documented dataset release. Do not treat the existence of a
reserved DOI as proof of publication.

## Dataset naming

**IWAS** is the correct project acronym. The initial Zenodo dataset record
uses “IWASS”, an editorial error retained in original deposited material;
the DOI is unchanged. The software's original module names are preserved
for reproducibility.

## Identifiers

Domain identifiers use unsalted SHA-256 of the original lower-case registrable
.it domain in UTF-8, matching the convention documented for the
[Italian Web Security Study](https://doi.org/10.5281/zenodo.21323346).

It is **pseudonymization, not anonymization**: a known-domain dictionary can
reproduce the hash. The candidate dataset also has rank information, which
may facilitate linkage. The released tables do not include raw URLs, page
titles, full DOM selectors or raw site HTML.

## Interpreting the counts

The original study has 10,022 targets; 7,573 produced evaluable findings,
and 2,449 did not. Of 36,038 page records on evaluable domains, 34,641
were successfully evaluated. An observed automated violation is evidence
of a specific detectable accessibility barrier, **not** a complete WCAG
conformance decision. Domains with failed evaluations are neither classified
as accessible nor inaccessible.

The [protocol](../protocol/methodology.md) documents sampling,
cross-domain redirects, collection errors, and the scope of automated
WCAG A/AA checks.
