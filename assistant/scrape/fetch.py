import re
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Error, Page, TimeoutError, sync_playwright

from assistant.config import settings
from assistant.logging import logger
from assistant.scrape.discover import (
    USER_AGENT,
    FetchText,
    absolute,
    allowed,
    internal,
    robots,
    sitemap_urls,
)
from assistant.scrape.document import pdf_title, pdf_to_markdown
from assistant.scrape.extract import page_document, to_markdown

DELAY_SECONDS = 1.0
TIMEOUT_MS = 45_000
MIN_MARKDOWN_CHARS = 200
# A mounted placeholder passes a "root has children" check, so rendering is
# judged by how much text arrived.
RENDERED = "document.body.innerText.trim().length > 500"
# Where a page has one, <main> excludes the header, mega-menu and footer.
CONTENT = "main"
RENDER_TIMEOUT_MS = 15_000
LINKS = "a[href]"
# A link-following crawl needs a stop.
MAX_PAGES = 120
DOWNLOAD_TIMEOUT_MS = 60_000


def crawl() -> int:
    """Render the site into knowledge/scraped/, following links as it goes.

    The site is a client-side application, so pages are rendered rather than
    fetched. The sitemap seeds the queue but does not bound it: it advertises
    paths that no longer resolve and omits pages that do, so links found on the
    rendered pages decide what is crawled.
    """
    settings.SCRAPED_DIR.mkdir(parents=True, exist_ok=True)
    written = 0

    with _page() as page:
        fetch = _text_fetcher(page)
        parser = robots(fetch)

        queue = [absolute(url, url) for url in sitemap_urls(fetch)]
        seen = set(queue)
        logger.info("Sitemap seeds %d pages", len(queue))

        while queue and len(seen) <= MAX_PAGES:
            url = queue.pop(0)

            if not allowed(parser, url):
                logger.info("robots.txt disallows %s", url)
                continue

            if url.lower().endswith(".pdf"):
                written += _save_pdf(page, url)
                time.sleep(DELAY_SECONDS)
                continue

            html = _render(page, url)
            time.sleep(DELAY_SECONDS)

            if html is None:
                continue

            written += _save(page, url, html)
            queue.extend(_undiscovered(page, url, seen))

    logger.info("Captured %d pages from %d visited", written, len(seen))
    return written


def _undiscovered(page: Page, url: str, seen: set[str]) -> list[str]:
    hrefs = page.eval_on_selector_all(
        LINKS, "elements => elements.map(element => element.getAttribute('href'))"
    )
    found: list[str] = []

    for href in hrefs:
        if not href:
            continue

        link = absolute(href, url)
        if link in seen or not internal(link):
            continue

        seen.add(link)
        found.append(link)

    return found


@contextmanager
def _page() -> Iterator[Page]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(user_agent=USER_AGENT)
        try:
            yield context.new_page()
        finally:
            browser.close()


def _text_fetcher(page: Page) -> FetchText:
    # By navigation, not `page.request`: the host serves an incomplete
    # certificate chain, and only Chromium completes it. Verification stays on.
    def fetch(url: str) -> str:
        response = page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        if response is None:
            raise RuntimeError(f"No response for {url}")
        return response.text()

    return fetch


def _save(page: Page, url: str, html: str) -> int:
    return _write(url, page.title(), to_markdown(html))


def _write(url: str, title: str, markdown: str) -> int:
    if len(markdown) < MIN_MARKDOWN_CHARS:
        logger.warning("%s produced almost no text", url)
        return 0

    path = settings.SCRAPED_DIR / f"{_slug(url)}.md"
    path.write_text(page_document(url, title, markdown))
    logger.info("Saved %s", path.name)
    return 1


def _save_pdf(page: Page, url: str) -> int:
    """Download the file and keep the text inside it.

    Navigating to a PDF raises instead of loading, but the download still
    starts, so the event carries the file the failed navigation did not.
    """
    with tempfile.TemporaryDirectory() as directory:
        try:
            with page.expect_download(timeout=DOWNLOAD_TIMEOUT_MS) as download:
                _ignoring_navigation_error(page, url)
            path = Path(directory) / "document.pdf"
            download.value.save_as(path)
            markdown = pdf_to_markdown(path)
            title = pdf_title(path, url)
        except Error as error:
            logger.warning("%s did not download: %s", url, _first_line(error))
            return 0

        return _write(url, title, markdown)


def _ignoring_navigation_error(page: Page, url: str) -> None:
    try:
        page.goto(url, timeout=DOWNLOAD_TIMEOUT_MS)
    except Error:
        return


def _render(page: Page, url: str) -> str | None:
    try:
        page.goto(url, wait_until="networkidle", timeout=TIMEOUT_MS)
    except Error as error:
        # One page that refuses to load costs that page, not the crawl.
        logger.warning("%s did not load: %s", url, _first_line(error))
        return None

    try:
        page.wait_for_function(RENDERED, timeout=RENDER_TIMEOUT_MS)
    except TimeoutError:
        logger.info("%s renders no content — skipping", url)
        return None

    if page.locator(CONTENT).count():
        return page.inner_html(CONTENT)

    return page.content()


def _first_line(error: Error) -> str:
    return error.message.splitlines()[0]


def _slug(url: str) -> str:
    path = url.rstrip("/").split("//", 1)[-1]
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", path).strip("-")
    return cleaned or "index"
