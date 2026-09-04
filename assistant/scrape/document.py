import re
from pathlib import Path

from pypdf import PdfReader

from assistant.scrape.extract import BLANK_LINES, WHITESPACE

MAX_PAGES = 60
AUTHORING_TOOL = re.compile(r"^Microsoft Word\s*-\s*", re.IGNORECASE)
WORD = re.compile(r"[A-Za-z]{3,}")


def pdf_to_markdown(path: Path) -> str:
    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages[:MAX_PAGES]]
    text = "\n\n".join(page.strip() for page in pages if page.strip())

    return BLANK_LINES.sub("\n\n", WHITESPACE.sub(" ", text)).strip()


def pdf_title(path: Path, url: str) -> str:
    """The document's own title where it is meaningful, else the file name.

    Exported PDFs often carry the authoring tool's placeholder — a tool name
    and a temporary file id — which names the document less than its URL does.
    """
    metadata = PdfReader(path).metadata
    title = AUTHORING_TOOL.sub("", (metadata.title or "").strip() if metadata else "")

    if not WORD.search(title):
        return _name(url)

    return title


def _name(url: str) -> str:
    stem = url.rstrip("/").split("/")[-1].removesuffix(".pdf")
    return stem.replace("-", " ").replace("%20", " ").strip()
