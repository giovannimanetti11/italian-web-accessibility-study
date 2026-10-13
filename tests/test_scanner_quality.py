from types import SimpleNamespace
from unittest.mock import Mock, call

from playwright.sync_api import Error as PlaywrightError

import iwass.scanner as scanner_module
from iwass.scanner import AccessibilityScanner, BrowserRecoveryError, _soft_block_reason


def test_rejected_http_200_content_detected():
    page = Mock()
    page.title.return_value = "Request Rejected"
    assert "request rejected" in _soft_block_reason(page)
    page.locator.assert_not_called()


def test_regular_page_not_soft_block():
    page = Mock()
    page.title.return_value = "Scuola Normale Superiore"
    page.locator("*").count.return_value = 1500
    assert _soft_block_reason(page) is None


def test_small_waf_error_body_detected():
    page = Mock()
    page.title.return_value = "Homepage"
    page.locator("*").count.return_value = 9
    page.locator("body").inner_text.return_value = (
        "The requested URL was rejected. Please consult with your administrator."
    )
    assert _soft_block_reason(page) == "blocked landing page body"


def test_no_successful_page_is_domain_error(monkeypatch):
    page = Mock()
    page.evaluate.return_value = "test-agent"
    page.url = "https://www.example.it/"
    context = Mock()
    context.new_page.return_value = page
    fake = AccessibilityScanner.__new__(AccessibilityScanner)
    fake._browser = SimpleNamespace(version="test-chromium", is_connected=lambda: True)
    fake.axe_version = "4.14.0"
    fake._new_context = lambda: context
    fake._open_homepage = lambda p, target: (SimpleNamespace(status=200), 1)
    fake._navigate = lambda p, target: (SimpleNamespace(status=404), 1)
    monkeypatch.setattr(scanner_module, "_soft_block_reason", lambda p: None)
    monkeypatch.setattr(scanner_module, "rendered_links", lambda *args: set())
    monkeypatch.setattr(scanner_module, "sitemap_urls", lambda *args: set())

    result = fake.scan_domain("example.it")
    assert result["status"] == "error"
    assert result["error"] == "no successfully evaluated sampled pages"
    assert len(result["pages"]) == 1
    assert result["pages"][0]["http_status"] == 404
    context.assert_has_calls([
        call.unroute_all(behavior="ignoreErrors"),
        call.close(),
    ])


def test_route_handler_aborts_malformed_idna_host_without_throwing():
    route = Mock()
    route.request.url = "https://invalid..example.it/tracker.js"
    fake = AccessibilityScanner.__new__(AccessibilityScanner)

    fake._route_handler(route)

    route.abort.assert_called_once_with()
    route.continue_.assert_not_called()


def test_route_handler_aborts_invalid_ipv6_url_without_throwing():
    route = Mock()
    route.request.url = "https://[not-ipv6]/resource"
    fake = AccessibilityScanner.__new__(AccessibilityScanner)

    fake._route_handler(route)

    route.abort.assert_called_once_with()
    route.continue_.assert_not_called()


def test_route_callback_does_not_propagate_closed_request_error():
    # Playwright can throw this TypeError while rewriting a late route error.
    route = Mock()
    route.request.url = "https://example.com/script.js"
    route.continue_.side_effect = TypeError(
        "Route.continue_: function takes exactly 5 arguments (1 given)"
    )
    fake = AccessibilityScanner.__new__(AccessibilityScanner)

    fake._route_handler(route)

    route.continue_.assert_called_once_with()


def test_crashed_unroute_and_close_do_not_stop_worker(monkeypatch):
    page = Mock()
    page.url = "https://example.it/"
    page.evaluate.return_value = "test-agent"
    context = Mock()
    context.new_page.return_value = page
    context.unroute_all.side_effect = PlaywrightError(
        "BrowserContext.unroute_all: Target crashed"
    )
    context.close.side_effect = PlaywrightError(
        "BrowserContext.close: Target crashed"
    )
    fake = AccessibilityScanner.__new__(AccessibilityScanner)
    fake._browser = Mock()
    fake._browser.is_connected.return_value = True
    fake._browser.version = "test-chromium"
    fake.axe_version = "4.14.0"
    fake._new_context = lambda: context
    fake._open_homepage = lambda p, target: (SimpleNamespace(status=200), 1)
    fake._navigate = lambda p, url: (SimpleNamespace(status=404), 1)
    monkeypatch.setattr(scanner_module, "_soft_block_reason", lambda p: None)
    monkeypatch.setattr(scanner_module, "rendered_links", lambda *args: set())
    monkeypatch.setattr(scanner_module, "sitemap_urls", lambda *args: set())

    result = fake.scan_domain("example.it")

    assert result["status"] == "error"
    assert result["error"] == "no successfully evaluated sampled pages"
    context.unroute_all.assert_called_once_with(behavior="ignoreErrors")
    context.close.assert_called_once_with()
    assert fake._browser_broken is True


def test_disconnected_chromium_is_relaunched_before_new_domain():
    fake = AccessibilityScanner.__new__(AccessibilityScanner)
    old_browser = Mock()
    old_browser.is_connected.return_value = False
    old_browser.close.side_effect = PlaywrightError("Target crashed")
    new_browser = Mock()
    fake._browser = old_browser
    fake._playwright = Mock()
    fake._playwright.chromium.launch.return_value = new_browser
    fake._domains_since_launch = 12

    fake._ensure_browser()

    fake._playwright.chromium.launch.assert_called_once_with(headless=True)
    assert fake._browser is new_browser
    assert fake._domains_since_launch == 0


def test_browser_is_periodically_recycled_before_resource_leak():
    fake = AccessibilityScanner.__new__(AccessibilityScanner)
    previous = Mock()
    previous.is_connected.return_value = True
    replacement = Mock()
    fake._browser = previous
    fake._playwright = Mock()
    fake._playwright.chromium.launch.return_value = replacement
    fake._domains_since_launch = 100

    fake._ensure_browser()

    previous.close.assert_called_once_with()
    assert fake._browser is replacement
    assert fake._domains_since_launch == 0


def test_context_creation_failure_is_domain_error_and_next_domain_can_recover():
    fake = AccessibilityScanner.__new__(AccessibilityScanner)
    fake._browser = Mock()
    fake._browser.is_connected.return_value = True
    fake._browser.version = "chromium"
    fake.axe_version = "4.14.0"
    fake._new_context = Mock(side_effect=PlaywrightError("Target crashed"))

    result = fake.scan_domain("example.it")

    assert result["status"] == "error"
    assert "Target crashed" in result["error"]
    assert result["requested_domain"] == "example.it"



def test_browser_restart_failure_is_not_counted_as_site_error():
    fake = AccessibilityScanner.__new__(AccessibilityScanner)
    fake._browser = Mock()
    fake._browser.is_connected.return_value = False
    fake._playwright = Mock()
    fake._playwright.chromium.launch.side_effect = PlaywrightError("Target crashed")
    fake.axe_version = "4.14.0"

    import pytest

    with pytest.raises(BrowserRecoveryError, match="Cannot restart Chromium"):
        fake.scan_domain("example.it")


def test_browser_connection_probe_error_triggers_relaunch():
    fake = AccessibilityScanner.__new__(AccessibilityScanner)
    fake._browser = Mock()
    fake._browser.is_connected.side_effect = PlaywrightError("Target crashed")
    fake._playwright = Mock()
    replacement = Mock()
    fake._playwright.chromium.launch.return_value = replacement

    fake._ensure_browser()

    assert fake._browser is replacement



def test_browser_restarted_after_renderer_crash_even_if_transport_connected():
    fake = AccessibilityScanner.__new__(AccessibilityScanner)
    old = Mock()
    old.is_connected.return_value = True
    new = Mock()
    fake._browser = old
    fake._playwright = Mock()
    fake._playwright.chromium.launch.return_value = new
    fake._browser_broken = True
    fake._domains_since_launch = 2

    fake._ensure_browser()

    assert fake._browser is new
    assert fake._browser_broken is False
