"""Frozen defaults for the v1.0 automated accessibility study."""

PROTOCOL_VERSION = "1.0.0"
MAX_PAGES_PER_DOMAIN = 5
NAVIGATION_TIMEOUT_MS = 30_000
POST_DOM_WAIT_MS = 1_500
SITEMAP_TIMEOUT_SECONDS = 12.0
MAX_SITEMAP_URLS = 5_000
MAX_SITEMAP_FILES = 8

VIEWPORT = {"width": 1366, "height": 768}
LOCALE = "it-IT"
TIMEZONE_ID = "Europe/Rome"

WCAG_TAGS = (
    "wcag2a",
    "wcag2aa",
    "wcag21a",
    "wcag21aa",
    "wcag22a",
    "wcag22aa",
)

FUNCTIONAL_HINTS = (
    "contact",
    "contatti",
    "contact-us",
    "prenota",
    "booking",
    "reservation",
    "login",
    "accedi",
    "search",
    "cerca",
    "checkout",
    "cart",
    "carrello",
    "preventivo",
    "quote",
)

CONTENT_HINTS = (
    "servizi",
    "services",
    "chi-siamo",
    "about",
    "news",
    "blog",
    "articoli",
    "article",
    "prodotto",
    "prodotti",
    "product",
    "products",
    "soluzioni",
    "solutions",
)

LOW_VALUE_HINTS = (
    "cookie-policy",
    "cookies-policy",
    "cookie",
    "cookies",
    "privacy-policy",
    "privacy",
    "termini",
    "terms",
    "condizioni",
    "note-legali",
    "legal",
    "impressum",
    "sitemap",
    "feed",
)

ACTION_PATH_HINTS = (
    "product_compare/add",
    "wishlist/add",
    "compare/add",
    "add-to-cart",
    "add_to_cart",
    "logout",
)

SKIP_EXTENSIONS = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".jpe",
        ".png",
        ".gif",
        ".webp",
        ".avif",
        ".bmp",
        ".tif",
        ".tiff",
        ".svg",
        ".ico",
        ".webm",
        ".mov",
        ".m4v",
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".zip",
        ".rar",
        ".gz",
        ".mp4",
        ".mp3",
        ".wav",
        ".woff",
        ".woff2",
        ".ttf",
        ".css",
        ".js",
        ".json",
        ".xml",
    }
)
