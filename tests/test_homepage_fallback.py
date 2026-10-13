from types import SimpleNamespace
from unittest.mock import Mock

from iwass.scanner import AccessibilityScanner


def make_scanner(attempts, statuses):
    scanner = AccessibilityScanner.__new__(AccessibilityScanner)

    def navigate(_page, url):
        attempts.append(url)
        response = statuses.get(url)
        if isinstance(response, Exception):
            raise response
        return SimpleNamespace(status=response), 1

    scanner._navigate = navigate
    return scanner


def test_apex_dns_failure_falls_back_to_www():
    attempts = []
    scanner = make_scanner(attempts, {
        "https://example.it": RuntimeError("non-public or unresolved"),
        "http://example.it": RuntimeError("non-public or unresolved"),
        "https://www.example.it": 200,
    })
    response, elapsed = scanner._open_homepage(Mock(), "example.it")
    assert response.status == 200 and elapsed == 1
    assert attempts == [
        "https://example.it",
        "http://example.it",
        "https://www.example.it",
    ]


def test_explicit_403_is_terminal_and_not_bypassed():
    attempts = []
    scanner = make_scanner(attempts, {"https://example.it": 403})
    response, _ = scanner._open_homepage(Mock(), "example.it")
    assert response.status == 403
    assert attempts == ["https://example.it"]


def test_www_site_does_not_grow_www_prefix():
    attempts = []
    scanner = make_scanner(attempts, {
        "https://www.example.it": RuntimeError("offline"),
        "http://www.example.it": 200,
    })
    scanner._open_homepage(Mock(), "www.example.it")
    assert all("www.www" not in url for url in attempts)
    assert attempts == ["https://www.example.it", "http://www.example.it"]
