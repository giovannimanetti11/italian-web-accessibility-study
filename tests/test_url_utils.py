from iwass.url_utils import (
    canonicalize_url,
    host_is_public,
    is_it_domain,
    registrable_domain,
    url_is_public,
)


def test_canonicalize_drops_tracking_and_fragment():
    value = canonicalize_url("HTTPS://WWW.Example.IT/a/?utm_source=x&b=2&a=1#fragment")
    assert value == "https://www.example.it/a?a=1&b=2"


def test_registrable_domain_handles_subdomains():
    assert registrable_domain("https://shop.example.it/path") == "example.it"


def test_it_scope():
    assert is_it_domain("https://www.example.it/")
    assert not is_it_domain("https://example.com/")


def test_malformed_port_is_rejected_without_exception():
    assert canonicalize_url("https://example.it:+390240702034/") == ""


def test_media_extensions_are_not_crawlable():
    from iwass.url_utils import crawlable_url

    assert not crawlable_url("https://example.it/uploads/photo.jpe", "example.it")
    assert not crawlable_url("https://example.it/video.webm", "example.it")


def test_invalid_idna_hostname_is_rejected_without_dns_exception():
    # Reproduces the worker-01 Playwright route crash (double-dot IDNA host).
    host_is_public.cache_clear()
    try:
        assert not url_is_public("https://subdomain..example.it/pixel.png")
    finally:
        host_is_public.cache_clear()


def test_malformed_ipv6_url_is_rejected_without_exception():
    assert not url_is_public("https://[not-ipv6]/resource")
