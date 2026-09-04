from collections.abc import Callable
from urllib.parse import urljoin, urlparse

from protego import Protego

BASE = "https://www.nawaloka.com"
ROBOTS = f"{BASE}/robots.txt"
SITEMAP = f"{BASE}/sitemap.xml"
USER_AGENT = "NawalokaAssistant/1.0 (+educational assignment; contact via repository)"

FetchText = Callable[[str], str]


def robots(fetch: FetchText) -> Protego:
    """Parse robots.txt from text the caller fetched.

    Not `urllib.robotparser`: it fetches through urllib, which cannot reach
    this host, and it matches rules first-wins, so a broad `Allow` masks the
    `Disallow` rules beneath it. Protego matches longest-first, as the standard
    requires, and understands `*` and `$`.
    """
    return Protego.parse(fetch(ROBOTS))


def sitemap_urls(fetch: FetchText) -> list[str]:
    return locations(fetch(SITEMAP))


def locations(xml: str) -> list[str]:
    urls: list[str] = []

    for fragment in xml.split("<loc>")[1:]:
        location, _, _ = fragment.partition("</loc>")
        cleaned = location.strip()
        if cleaned:
            urls.append(cleaned)

    return urls


def allowed(parser: Protego, url: str) -> bool:
    return parser.can_fetch(url, USER_AGENT)


def internal(url: str) -> bool:
    """Same host and scheme: what keeps a link-following crawl on the site."""
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and parsed.netloc == urlparse(BASE).netloc


def absolute(href: str, base: str) -> str:
    """Resolve a link against its page, dropping the fragment.

    A fragment addresses a position within a page already crawled, not another
    page.
    """
    return urljoin(base, href).split("#")[0].rstrip("/") or BASE
