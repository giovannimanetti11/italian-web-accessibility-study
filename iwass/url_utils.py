from __future__ import annotations

import ipaddress
import socket
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import tldextract

from iwass.config import SKIP_EXTENSIONS

_extract = tldextract.TLDExtract(suffix_list_urls=())
_TRACKING_KEYS = {
    "fbclid",
    "gclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
}


def ensure_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if "://" not in value:
        return "https://" + value
    return value


def registrable_domain(value: str) -> str:
    parsed = urlparse(ensure_url(value))
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        return ""
    result = _extract(host)
    if result.domain and result.suffix:
        return f"{result.domain}.{result.suffix}"
    return host


def canonicalize_url(value: str, base: str | None = None) -> str:
    raw = value.strip()
    if base:
        raw = urljoin(base, raw)
    raw = ensure_url(raw)
    if not raw:
        return ""

    parsed = urlparse(raw)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower().rstrip(".")
    if scheme not in {"http", "https"} or not host:
        return ""

    try:
        port = parsed.port
    except ValueError:
        return ""
    netloc = host
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        netloc = f"{host}:{port}"

    path = parsed.path or "/"
    while "//" in path:
        path = path.replace("//", "/")
    if path != "/":
        path = path.rstrip("/")

    query_items = []
    for key, val in parse_qsl(parsed.query, keep_blank_values=True):
        lower = key.lower()
        if lower.startswith("utm_") or lower in _TRACKING_KEYS:
            continue
        query_items.append((key, val))
    query = urlencode(sorted(query_items))

    return urlunparse((scheme, netloc, path, "", query, ""))


def same_site(url: str, scope_domain: str) -> bool:
    return bool(scope_domain and registrable_domain(url) == scope_domain)


def crawlable_url(url: str, scope_domain: str) -> bool:
    canonical = canonicalize_url(url)
    if not canonical or not same_site(canonical, scope_domain):
        return False
    parsed = urlparse(canonical)
    path = parsed.path.lower()
    if any(path.endswith(ext) for ext in SKIP_EXTENSIONS):
        return False
    if path.startswith(("/wp-admin/", "/wp-json/", "/cdn-cgi/", "/.well-known/")):
        return False
    return True


def is_it_domain(value: str) -> bool:
    return registrable_domain(value).endswith(".it")


@lru_cache(maxsize=4096)
def host_is_public(host: str) -> bool:
    try:
        addresses = socket.getaddrinfo(host, None)
    except (OSError, UnicodeError, ValueError):
        # Broken IDNA labels (e.g. foo..example.it) raise UnicodeEncodeError.
        # Such resource requests must be denied, not crash the Playwright route.
        return False
    ips = {item[4][0] for item in addresses}
    if not ips:
        return False
    for raw in ips:
        try:
            ip = ipaddress.ip_address(raw)
        except ValueError:
            return False
        if not ip.is_global:
            return False
    return True


def url_is_public(value: str) -> bool:
    try:
        parsed = urlparse(ensure_url(value))
        host = (parsed.hostname or "").lower()
    except (ValueError, UnicodeError):
        return False
    return bool(host and host_is_public(host))
