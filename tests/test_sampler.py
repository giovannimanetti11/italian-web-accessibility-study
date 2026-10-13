from iwass.sampler import select_pages


def test_sampling_is_deterministic_and_bounded():
    links = [
        "https://example.it/contatti",
        "https://example.it/servizi",
        "https://example.it/a/b/c",
        "https://example.it/news/uno",
        "https://example.it/news/due",
        "https://example.it/prodotto/1",
    ]
    first = select_pages("example.it", "https://example.it/", links)
    second = select_pages("example.it", "https://example.it/", list(reversed(links)))

    assert first == second
    assert len(first) == 5
    assert first[0].reason == "homepage"
    assert {item.reason for item in first} >= {"functional", "content", "deep"}


def test_sampling_does_not_leave_scope():
    pages = select_pages(
        "example.it",
        "https://example.it/",
        ["https://other.it/foo", "https://example.it/ok"],
    )
    assert all("example.it" in item.url for item in pages)


def test_functional_hints_use_word_boundaries():
    links = [
        "https://example.it/collections/cartier",
        "https://example.it/filtri-a-cartuccia",
        "https://example.it/cartosio",
        "https://example.it/cart",
        "https://example.it/contatti",
    ]
    pages = select_pages("example.it", "https://example.it/", links)
    functional = [page.url for page in pages if page.reason == "functional"]
    assert len(functional) == 1
    assert functional[0] in {"https://example.it/cart", "https://example.it/contatti"}


def test_functional_hint_inside_product_slug_is_not_functional():
    links = [
        (
            "https://example.it/accessori-e-ricambi/"
            "7799-pressostato-di-massima-a-2-contatti-1-4.html"
        ),
        "https://example.it/prodotti/filtro",
        "https://example.it/blog/articolo",
        "https://example.it/faqs/richiesta-tecnica",
        "https://example.it/contatti",
    ]
    pages = select_pages("example.it", "https://example.it/", links)
    functional = [page.url for page in pages if page.reason == "functional"]
    assert functional == ["https://example.it/contatti"]


def test_article_slug_starting_with_carrello_is_not_functional():
    links = [
        "https://example.it/carrello-sterilizzato-il-gruppo-conad",
        "https://example.it/blog/notizia",
        "https://example.it/servizi",
        "https://example.it/contatti",
    ]
    pages = select_pages("example.it", "https://example.it/", links)
    functional = [page.url for page in pages if page.reason == "functional"]
    assert functional == ["https://example.it/contatti"]


def test_quote_maggiorate_is_not_functional():
    links = [
        "https://example.it/promo/sport/quote-maggiorate",
        "https://example.it/account/quote/create",
        "https://example.it/prodotto/1",
        "https://example.it/news/uno",
    ]
    pages = select_pages("example.it", "https://example.it/", links)
    functional = [page.url for page in pages if page.reason == "functional"]
    assert functional == ["https://example.it/account/quote/create"]


def test_low_value_legal_pages_are_not_sampled_when_alternatives_exist():
    links = [
        "https://example.it/privacy-policy",
        "https://example.it/cookie-policy",
        "https://example.it/servizi",
        "https://example.it/news/articolo",
        "https://example.it/contatti",
        "https://example.it/prodotto/1",
        "https://example.it/prodotto/2",
    ]
    pages = select_pages("example.it", "https://example.it/", links)
    urls = {page.url for page in pages}
    assert "https://example.it/privacy-policy" not in urls
    assert "https://example.it/cookie-policy" not in urls


def test_cms_json_query_is_not_classified_as_functional_search():
    links = [
        'https://example.it/it?b_size=33&query=%5B%7B%22i%22%3A%22portal_type%22%7D%5D',
        'https://example.it/contatti',
        'https://example.it/servizi',
        'https://example.it/blog/post',
        'https://example.it/cerca?q=accessibilita',
    ]
    pages = select_pages('example.it', 'https://example.it/', links)
    functional = [page.url for page in pages if page.reason == 'functional']
    assert len(functional) == 1
    assert 'portal_type' not in functional[0]


def test_generic_policy_notice_is_not_sampled():
    links = [
        "https://example.it/_/_/policy/notice-at-collection",
        "https://example.it/servizi",
        "https://example.it/contatti",
        "https://example.it/blog/articolo",
        "https://example.it/offerta/a/b",
        "https://example.it/altro",
    ]
    pages = select_pages("example.it", "https://example.it/", links)
    assert not any("/policy/" in page.url for page in pages)
    assert {page.reason for page in pages} >= {"homepage", "functional", "content"}


def test_cookie_plural_and_action_urls_are_excluded():
    links = [
        "https://example.it/cookies_policy",
        "https://example.it/catalog/product_compare/add/product/123",
        "https://example.it/wishlist/add/item/42",
        "https://example.it/prodotto/1",
        "https://example.it/prodotto/2",
        "https://example.it/news/uno",
        "https://example.it/contatti",
    ]
    pages = select_pages("example.it", "https://example.it/", links)
    urls = {page.url for page in pages}
    assert "https://example.it/cookies_policy" not in urls
    assert not any("product_compare/add" in url for url in urls)
    assert not any("wishlist/add" in url for url in urls)
