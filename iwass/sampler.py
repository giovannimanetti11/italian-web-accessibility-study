from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlparse

from iwass.config import (
    ACTION_PATH_HINTS,
    CONTENT_HINTS,
    FUNCTIONAL_HINTS,
    LOW_VALUE_HINTS,
    MAX_PAGES_PER_DOMAIN,
)
from iwass.models import SampledPage
from iwass.url_utils import canonicalize_url, crawlable_url


def _path_depth(url: str) -> int:
    return len([part for part in urlparse(url).path.split("/") if part])


def _normal_words(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def _contains_hint(url: str, hints: tuple[str, ...]) -> bool:
    parsed = urlparse(url)
    haystack = f" {_normal_words(parsed.path + ' ' + parsed.query)} "
    for hint in hints:
        needle = _normal_words(hint)
        if needle and f" {needle} " in haystack:
            return True
    return False


def _functional_match(url: str) -> bool:
    parsed = urlparse(url)
    segments = [_normal_words(part) for part in parsed.path.split("/") if part]
    query_pairs = dict(parse_qsl(parsed.query, keep_blank_values=True))

    exact_hints = {_normal_words(hint) for hint in FUNCTIONAL_HINTS}
    short_prefix_hints = {
        "contact",
        "contatti",
        "prenota",
        "booking",
        "login",
        "search",
        "cerca",
        "checkout",
    }

    for segment in segments:
        if segment in exact_hints:
            return True
        words = segment.split()
        if len(words) <= 3 and any(
            segment.startswith(prefix + " ") for prefix in short_prefix_hints
        ):
            return True

    for key, value in query_pairs.items():
        if _normal_words(key) in {"search", "query", "q"}:
            # CMS listing filters often serialize JSON into ?query=[...];
            # these are not user-facing search pages.
            if not value.lstrip().startswith(("[", "{")):
                return True
    return False


def _is_low_value(url: str) -> bool:
    parsed = urlparse(url)
    normalized_path = _normal_words(parsed.path)
    if any(_normal_words(hint) in normalized_path for hint in LOW_VALUE_HINTS):
        return True
    segments = {part.lower() for part in parsed.path.split("/") if part}
    # Legal notices often appear under generic /policy/... routes that would
    # otherwise win the deep-page selection without representing the product.
    if segments & {"policy", "policies", "notice-at-collection"}:
        return True
    raw_path = parsed.path.lower()
    return any(hint in raw_path for hint in ACTION_PATH_HINTS)


def _hash_rank(domain: str, label: str, url: str) -> str:
    payload = f"{domain}|{label}|{url}".encode()
    return hashlib.sha256(payload).hexdigest()


def _pick(domain: str, label: str, urls: list[str]) -> str | None:
    if not urls:
        return None
    return min(urls, key=lambda url: _hash_rank(domain, label, url))


def select_pages(
    domain: str,
    homepage_url: str,
    discovered_urls: list[str] | set[str],
    max_pages: int = MAX_PAGES_PER_DOMAIN,
) -> list[SampledPage]:
    homepage = canonicalize_url(homepage_url)
    pool = sorted(
        {
            canonicalize_url(url)
            for url in discovered_urls
            if canonicalize_url(url)
            and canonicalize_url(url) != homepage
            and crawlable_url(canonicalize_url(url), domain)
            and not _is_low_value(canonicalize_url(url))
        }
    )

    selected: list[tuple[str, str]] = [(homepage, "homepage")]
    used = {homepage}

    def add_category(reason: str, predicate) -> None:
        candidates = [url for url in pool if url not in used and predicate(url)]
        choice = _pick(domain, reason, candidates)
        if choice:
            selected.append((choice, reason))
            used.add(choice)

    add_category("functional", _functional_match)
    add_category("content", lambda url: _contains_hint(url, CONTENT_HINTS))

    deep_candidates = [url for url in pool if url not in used]
    if deep_candidates:
        max_depth = max(_path_depth(url) for url in deep_candidates)
        deepest = [url for url in deep_candidates if _path_depth(url) == max_depth]
        choice = _pick(domain, "deep", deepest)
        if choice:
            selected.append((choice, "deep"))
            used.add(choice)

    seeded_candidates = [url for url in pool if url not in used]
    choice = _pick(domain, "seeded", seeded_candidates)
    if choice:
        selected.append((choice, "seeded"))
        used.add(choice)

    slot = 0
    while len(selected) < max_pages:
        remaining = [url for url in pool if url not in used]
        if not remaining:
            break
        choice = _pick(domain, f"fallback-{slot}", remaining)
        if not choice:
            break
        selected.append((choice, "fallback"))
        used.add(choice)
        slot += 1

    return [
        SampledPage(domain=domain, url=url, reason=reason, rank=index)
        for index, (url, reason) in enumerate(selected[:max_pages])
    ]
