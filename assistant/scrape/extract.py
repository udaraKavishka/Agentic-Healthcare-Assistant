import re
from html.parser import HTMLParser

SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer", "header"}
BLOCK_TAGS = {"p", "div", "section", "article", "li", "br", "tr"}
HEADING_TAGS = {"h1": "#", "h2": "##", "h3": "###", "h4": "####"}
WHITESPACE = re.compile(r"[ \t]+")
BLANK_LINES = re.compile(r"\n{3,}")


class _Markdown(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0
        self._heading: str | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag in HEADING_TAGS:
            self._heading = HEADING_TAGS[tag]
            self.parts.append(f"\n\n{HEADING_TAGS[tag]} ")
            return
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag in HEADING_TAGS:
            self._heading = None
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = WHITESPACE.sub(" ", data).strip()
        if text:
            self.parts.append(text if self._heading else f"{text} ")


def to_markdown(html: str) -> str:
    parser = _Markdown()
    parser.feed(html)
    return BLANK_LINES.sub("\n\n", "".join(parser.parts)).strip()


def page_document(url: str, title: str, markdown: str) -> str:
    """Front matter keeps the source URL with the text, so citations survive."""
    return f"---\nurl: {url}\ntitle: {title}\n---\n\n{markdown}\n"
