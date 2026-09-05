from dataclasses import dataclass

from assistant.config import settings


@dataclass(frozen=True)
class Page:
    """One scraped page, with its front matter read off the top."""

    url: str
    title: str
    body: str


def pages() -> list[Page]:
    """Every scraped page, in a stable order.

    Indexing and FAQ harvesting both walk the same corpus, so the front matter
    is parsed in one place and neither can disagree about a page's URL.
    """
    return [
        _page(path.read_text(), fallback=path.stem)
        for path in sorted(settings.SCRAPED_DIR.glob("*.md"))
    ]


def _page(text: str, fallback: str) -> Page:
    url, title, body = _split_front_matter(text)

    return Page(url=url or fallback, title=title or fallback, body=body)


def _split_front_matter(text: str) -> tuple[str, str, str]:
    if not text.startswith("---"):
        return "", "", text

    _, _, rest = text.partition("---")
    front, _, body = rest.partition("---")

    url = title = ""
    for line in front.splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "url":
            url = value.strip()
        if key.strip() == "title":
            title = value.strip()

    return url, title, body
