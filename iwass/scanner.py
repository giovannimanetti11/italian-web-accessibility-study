from __future__ import annotations

import hashlib
import logging
import platform
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from iwass.axe import axe_assets, run_axe
from iwass.config import (
    LOCALE,
    NAVIGATION_TIMEOUT_MS,
    POST_DOM_WAIT_MS,
    PROTOCOL_VERSION,
    TIMEZONE_ID,
    VIEWPORT,
    WCAG_TAGS,
)
from iwass.discovery import rendered_links, sitemap_urls
from iwass.sampler import select_pages
from iwass.storage import utc_now
from iwass.url_utils import (
    canonicalize_url,
    ensure_url,
    registrable_domain,
    url_is_public,
)

_log = logging.getLogger(__name__)


class BrowserRecoveryError(RuntimeError):
    """A browser infrastructure failure; do not score the target as a site error."""


def _soft_block_reason(page) -> str | None:
    """Recognize obvious successful-HTTP bot/WAF error pages.

    Keep this intentionally conservative: unknown challenges must be reviewed
    separately rather than inferring them from small normal web pages.
    """
    title = (page.title() or "").strip().casefold()
    blocked_titles = {
        "request rejected", "access denied", "just a moment...",
        "just a moment", "attention required! | cloudflare", "captcha challenge",
    }
    if title in blocked_titles or title.startswith("attention required! | cloudflare"):
        return f"blocked landing page title: {title}"
    if page.locator("*").count() <= 60:
        body = page.locator("body").inner_text(timeout=2000).casefold()
        if any(needle in body for needle in (
            "the requested url was rejected", "your request has been blocked",
            "you have been blocked from accessing",
        )):
            return "blocked landing page body"
    return None


def _document_metadata(page) -> tuple[str | None, str | None]:
    title = page.title() or None
    lang = page.evaluate(
        "() => document.documentElement ? (document.documentElement.lang || null) : null"
    )
    return title, lang


class AccessibilityScanner:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self._playwright = None
        self._browser = None
        self.axe_path, self.axe_version = axe_assets(repo_root)

    # Restart the same pinned Chromium build at fixed intervals to avoid
    # unbounded long-lived browser state during multi-thousand-domain crawls.
    MAX_DOMAINS_PER_BROWSER = 100

    def __enter__(self):
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._domains_since_launch = 0
        self._browser_broken = False
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._browser:
                try:
                    self._browser.close()
                except (PlaywrightError, TypeError) as error:
                    _log.warning("Browser close after crash: %s", error)
        finally:
            if self._playwright:
                try:
                    self._playwright.stop()
                except (PlaywrightError, TypeError) as error:
                    _log.warning("Playwright driver stop after crash: %s", error)

    def _ensure_browser(self):
        """Recover from Chromium crashes and periodically recycle the browser."""
        count = getattr(self, "_domains_since_launch", 0)
        try:
            connected = self._browser is not None and self._browser.is_connected()
        except (PlaywrightError, TypeError):
            connected = False
        if (connected and count < self.MAX_DOMAINS_PER_BROWSER
                and not getattr(self, "_browser_broken", False)):
            return
        if self._browser:
            try:
                self._browser.close()
            except (PlaywrightError, TypeError) as error:
                _log.warning("Discarding crashed Chromium instance: %s", error)
        # Preserve the same Python, Playwright and Chromium versions. No
        # altered page-selection or network policy is involved in recovery.
        try:
            self._browser = self._playwright.chromium.launch(headless=True)
        except (PlaywrightError, TypeError) as error:
            raise BrowserRecoveryError(f"Cannot restart Chromium: {error}") from error
        self._domains_since_launch = 0
        self._browser_broken = False

    @property
    def chromium_version(self) -> str:
        return self._browser.version if self._browser else "unknown"

    def _route_handler(self, route) -> None:
        # Fail closed for malformed or non-public resource URLs, including
        # invalid IDNA labels injected by third-party scripts.
        url = route.request.url
        try:
            try:
                scheme = urlparse(url).scheme
            except (ValueError, UnicodeError):
                scheme = ""
            if scheme in {"data", "blob", "about"}:
                route.continue_()
            elif scheme not in {"http", "https"} or not url_is_public(url):
                route.abort()
            else:
                route.continue_()
        except (PlaywrightError, TypeError) as exc:
            # A request can disappear between interception and continue/abort.
            # Playwright 1.63 may also incorrectly re-wrap the transport failure
            # as TypeError("Route.continue_: function takes exactly 5 arguments").
            if isinstance(exc, TypeError) and not (
                "Route.continue_:" in str(exc) or "Route.abort:" in str(exc)
            ):
                raise
            _log.warning("Playwright route ended before handling: %s", exc)

    def _new_context(self):
        context = self._browser.new_context(
            viewport=VIEWPORT,
            locale=LOCALE,
            timezone_id=TIMEZONE_ID,
            java_script_enabled=True,
        )
        context.add_init_script(path=str(self.axe_path))
        context.route("**/*", self._route_handler)
        return context

    def _navigate(self, page, url: str):
        if not url_is_public(url):
            raise RuntimeError(f"non-public or unresolved URL rejected: {url}")
        started = time.monotonic()
        response = page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=NAVIGATION_TIMEOUT_MS,
        )
        page.wait_for_timeout(POST_DOM_WAIT_MS)
        elapsed_ms = round((time.monotonic() - started) * 1000)
        return response, elapsed_ms

    def _open_homepage(self, page, target: str):
        https_url = ensure_url(target)
        if https_url.startswith("http://"):
            candidates = [https_url]
        else:
            candidates = [https_url]
            if https_url.startswith("https://"):
                candidates.append("http://" + https_url.removeprefix("https://"))

        # Many .it domains have no apex DNS record, yet their public www host
        # works. Only try a conventional www hostname for the original apex.
        # Explicit 4xx responses remain terminal (do not evade access controls).
        parsed = urlparse(https_url)
        if parsed.hostname and parsed.hostname == registrable_domain(https_url):
            original_host = parsed.netloc
            for candidate in tuple(candidates):
                if original_host and urlparse(candidate).netloc == original_host:
                    candidates.append(candidate.replace(
                        "://" + original_host, "://www." + original_host, 1
                    ))

        last_error = None
        for candidate in candidates:
            try:
                response, elapsed = self._navigate(page, candidate)
                if response and response.status < 500:
                    return response, elapsed
                if response:
                    last_error = RuntimeError(f"HTTP {response.status} at {candidate}")
            except (PlaywrightError, PlaywrightTimeoutError, RuntimeError) as exc:
                last_error = exc
        raise RuntimeError(str(last_error or "homepage navigation failed"))

    def _scan_loaded_page(self, page, sampled, response, load_time_ms: int) -> dict:
        soft_block = _soft_block_reason(page)
        if soft_block:
            raise RuntimeError(f"soft_block: {soft_block}")
        html = page.content()
        title, lang = _document_metadata(page)
        final_url = canonicalize_url(page.url)
        record = {
            **sampled.to_dict(),
            "final_url": final_url,
            "http_status": response.status if response else None,
            "load_time_ms": load_time_ms,
            "title": title,
            "lang": lang,
            "dom_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
            "dom_nodes": page.locator("*").count(),
            "scanned_at": utc_now(),
            "axe_version": self.axe_version,
            "chromium_version": self.chromium_version,
            "wcag_tags": list(WCAG_TAGS),
        }
        record.update(run_axe(page))
        return record

    def scan_domain(self, target: str) -> dict:
        domain_timer = time.monotonic()
        requested_url = ensure_url(target)
        requested_domain = registrable_domain(requested_url)
        started_at = utc_now()
        context = None

        try:
            self._ensure_browser()
            self._domains_since_launch = getattr(self, "_domains_since_launch", 0) + 1
            context = self._new_context()
            page = context.new_page()
            actual_user_agent = page.evaluate("() => navigator.userAgent")
            home_response, home_elapsed = self._open_homepage(page, requested_url)
            if not home_response or home_response.status >= 400:
                code = home_response.status if home_response else "no response"
                raise RuntimeError(f"homepage returned {code}")
            soft_block = _soft_block_reason(page)
            if soft_block:
                raise RuntimeError(f"homepage soft_block: {soft_block}")

            final_home = canonicalize_url(page.url)
            scope_domain = registrable_domain(final_home)
            if not scope_domain:
                raise RuntimeError("could not determine final registrable domain")

            discovery_timer = time.monotonic()
            home_links = rendered_links(page, final_home, scope_domain)
            sitemap_timer = time.monotonic()
            map_links = sitemap_urls(final_home, scope_domain, actual_user_agent)
            sitemap_discovery_ms = round((time.monotonic() - sitemap_timer) * 1000)
            candidates = home_links | map_links
            sampled = select_pages(scope_domain, final_home, candidates)
            discovery_total_ms = round((time.monotonic() - discovery_timer) * 1000)

            pages = []
            for item in sampled:
                try:
                    response, elapsed = self._navigate(page, item.url)
                    if response and response.status < 400:
                        pages.append(self._scan_loaded_page(page, item, response, elapsed))
                    else:
                        pages.append(
                            {
                                **item.to_dict(),
                                "final_url": canonicalize_url(page.url),
                                "http_status": response.status if response else None,
                                "load_time_ms": elapsed,
                                "error": "non-success HTTP status",
                                "scanned_at": utc_now(),
                            }
                        )
                except Exception as exc:
                    pages.append(
                        {
                            **item.to_dict(),
                            "final_url": None,
                            "http_status": None,
                            "error": f"{type(exc).__name__}: {exc}",
                            "scanned_at": utc_now(),
                        }
                    )

            # A reachable homepage is not enough: an all-failed page sample
            # must not inflate the number of accessible/evaluable domains.
            successfully_evaluated = any(not result.get("error") for result in pages)
            return {
                "status": "complete" if successfully_evaluated else "error",
                "error": (
                    None if successfully_evaluated else "no successfully evaluated sampled pages"
                ),
                "protocol_version": PROTOCOL_VERSION,
                "requested_target": target,
                "requested_domain": requested_domain,
                "final_homepage": final_home,
                "scope_domain": scope_domain,
                "redirected_cross_domain": requested_domain != scope_domain,
                "started_at": started_at,
                "completed_at": utc_now(),
                "discovery": {
                    "rendered_homepage_links": len(home_links),
                    "sitemap_urls": len(map_links),
                    "candidate_urls": len(candidates),
                    "sampled_pages": len(sampled),
                },
                "timings": {
                    "homepage_load_ms": home_elapsed,
                    "sitemap_discovery_ms": sitemap_discovery_ms,
                    "discovery_total_ms": discovery_total_ms,
                    "domain_total_ms": round((time.monotonic() - domain_timer) * 1000),
                },
                "manifest": [item.to_dict() for item in sampled],
                "pages": pages,
                "environment": {
                    "protocol_version": PROTOCOL_VERSION,
                    "axe_version": self.axe_version,
                    "chromium_version": self.chromium_version,
                    "viewport": VIEWPORT,
                    "locale": LOCALE,
                    "timezone_id": TIMEZONE_ID,
                    "user_agent": actual_user_agent,
                    "navigation_timeout_ms": NAVIGATION_TIMEOUT_MS,
                    "post_dom_wait_ms": POST_DOM_WAIT_MS,
                    "platform": platform.platform(),
                    "python_version": sys.version.split()[0],
                },
            }
        except BrowserRecoveryError:
            # Do not fill thousands of domain error records when the driver
            # is broken. Let the bounded worker supervisor restart the process.
            raise
        except Exception as exc:
            return {
                "status": "error",
                "protocol_version": PROTOCOL_VERSION,
                "requested_target": target,
                "requested_domain": requested_domain,
                "started_at": started_at,
                "completed_at": utc_now(),
                "error": f"{type(exc).__name__}: {exc}",
                "timings": {
                    "domain_total_ms": round((time.monotonic() - domain_timer) * 1000),
                },
                "environment": {
                    "axe_version": self.axe_version,
                    "chromium_version": self.chromium_version,
                },
            }
        finally:
            if context is not None:
                # Cleanup is best effort after a Chromium crash. A failed
                # unroute/close must not discard a domain result or kill
                # the worker, and a disconnected browser is relaunched on
                # the following scan_domain call.
                try:
                    context.unroute_all(behavior="ignoreErrors")
                except (PlaywrightError, TypeError) as error:
                    if "crash" in str(error).lower():
                        self._browser_broken = True
                    _log.warning("Chromium context unroute after crash: %s", error)
                try:
                    context.close()
                except (PlaywrightError, TypeError) as error:
                    if "crash" in str(error).lower():
                        self._browser_broken = True
                    _log.warning("Chromium context close after crash: %s", error)
