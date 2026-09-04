import re
from dataclasses import dataclass

HEADING = re.compile(r"^(#{1,4})\s+(.*)$", re.MULTILINE)
MAX_CHARS = 1200
MIN_CHARS = 80


@dataclass
class Chunk:
    text: str
    heading: str
    url: str
    title: str


def chunk_page(markdown: str, url: str, title: str) -> list[Chunk]:
    """Split on heading structure rather than a fixed character count.

    These are templated marketing pages whose headings already mark topic
    boundaries, so semantic chunking would spend embedding calls rediscovering
    structure the HTML hands over for free.
    """
    sections = _split_on_headings(markdown)
    chunks: list[Chunk] = []

    for heading, body in sections:
        for part in _split_long(body):
            if len(part.strip()) < MIN_CHARS:
                continue
            chunks.append(
                Chunk(text=part.strip(), heading=heading, url=url, title=title)
            )

    return chunks


def _split_on_headings(markdown: str) -> list[tuple[str, str]]:
    matches = list(HEADING.finditer(markdown))
    if not matches:
        return [("", markdown)]

    sections: list[tuple[str, str]] = []
    preamble = markdown[: matches[0].start()].strip()
    if preamble:
        sections.append(("", preamble))

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        sections.append((match.group(2).strip(), markdown[match.end() : end]))

    return sections


def _split_long(body: str) -> list[str]:
    if len(body) <= MAX_CHARS:
        return [body]

    parts: list[str] = []
    current = ""
    for paragraph in body.split("\n\n"):
        if len(current) + len(paragraph) > MAX_CHARS and current:
            parts.append(current)
            current = paragraph
            continue
        current = f"{current}\n\n{paragraph}" if current else paragraph

    if current:
        parts.append(current)
    return parts
