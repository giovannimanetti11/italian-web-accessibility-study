from __future__ import annotations

from collections import deque
from urllib.parse import urljoin

import httpx
from defusedxml import ElementTree

from iwass.config import (
    MAX_SITEMAP_FILES,
    MAX_SITEMAP_URLS,
    SITEMAP_TIMEOUT_SECONDS,
)
from iwass.url_utils import canonicalize_url, crawlable_url, url_is_public


def rendered_links(page, base_url: str, scope_domain: str) -> set[str]:
    hrefs = page.eval_on_selector_all(
        "a[href]",
        "(nodes) => nodes.map((node) => node.href).filter(Boolean)",
    )
    links = set()
    for href in hrefs:
        url = canonicalize_url(str(href), base=base_url)
        if url and crawlable_url(url, scope_domain):
            links.add(url)
    return links


def _safe_get(client: httpx.Client, url: str, max_redirects: int = 3) -> httpx.Response | None:
    current = url
    for _ in range(max_redirects + 1):
        if not url_is_public(current):
            return None
        try:
            response = client.get(current, follow_redirects=False)
        except httpx.HTTPError:
            return None
        if response.status_code not in {301, 302, 303, 307, 308}:
            return response
        location = response.headers.get("location")
        if not location:
            return response
        current = urljoin(current, location)
    return None


def _xml_locations(xml_text: str) -> tuple[str, list[str]]:
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return "invalid", []

    root_name = root.tag.rsplit("}", 1)[-1].lower()
    locations = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1].lower() == "loc" and element.text:
            locations.append(element.text.strip())
    return root_name, locations


def sitemap_urls(home_url: str, scope_domain: str, user_agent: str) -> set[str]:
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/plain,application/xml,text/xml,*/*;q=0.5",
    }
    timeout = httpx.Timeout(SITEMAP_TIMEOUT_SECONDS)
    seeds = {
        urljoin(home_url, "/sitemap.xml"),
        urljoin(home_url, "/sitemap_index.xml"),
    }

    with httpx.Client(headers=headers, timeout=timeout) as client:
        robots = _safe_get(client, urljoin(home_url, "/robots.txt"))
        if robots and robots.status_code == 200:
            for line in robots.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    seeds.add(line.split(":", 1)[1].strip())

        queue = deque(sorted(seeds))
        seen_sitemaps: set[str] = set()
        found: set[str] = set()

        while queue and len(seen_sitemaps) < MAX_SITEMAP_FILES and len(found) < MAX_SITEMAP_URLS:
            sitemap = canonicalize_url(queue.popleft())
            if not sitemap or sitemap in seen_sitemaps:
                continue
            seen_sitemaps.add(sitemap)
            response = _safe_get(client, sitemap)
            if not response or response.status_code != 200:
                continue

            root_name, locations = _xml_locations(response.text)
            if root_name == "sitemapindex":
                for child in sorted(locations):
                    child_url = canonicalize_url(child, base=sitemap)
                    if child_url and child_url not in seen_sitemaps:
                        queue.append(child_url)
            elif root_name == "urlset":
                for raw in locations:
                    url = canonicalize_url(raw, base=sitemap)
                    if url and crawlable_url(url, scope_domain):
                        found.add(url)
                        if len(found) >= MAX_SITEMAP_URLS:
                            break

    return found
