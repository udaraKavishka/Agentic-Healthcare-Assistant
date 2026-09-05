import re
from dataclasses import dataclass

import yaml

from assistant.config import settings
from assistant.knowledge_base.corpus import Page, pages
from assistant.logging import logger

HEADING = re.compile(r"^(#{1,4})\s+(.*)$", re.MULTILINE)
FAQ_HEADING = re.compile(r"frequently asked questions|^faqs?\b", re.IGNORECASE)
# "### 3. What information is needed?" is one question, not a numbered list.
NUMBERING = re.compile(r"^\d+[.)]\s*")
MIN_ANSWER_CHARS = 40
MAX_ANSWER_CHARS = 700


@dataclass(frozen=True)
class Harvested:
    question: str
    answer: str
    source: str


def harvest() -> int:
    """Write the FAQ sections the hospital publishes into the fast path.

    Hand-written FAQs go stale the moment the hospital changes a policy, and
    nobody remembers to edit a YAML file in this repository when they do. The
    website already carries the questions patients ask, so they are collected
    from the corpus and refresh with it.
    """
    found = [item for page in pages() for item in _from_page(page)]
    rows = [
        {"question": item.question, "answer": item.answer, "source": item.source}
        for item in _deduplicated(found)
    ]

    settings.HARVESTED_FAQ_PATH.write_text(
        yaml.safe_dump(rows, sort_keys=False, allow_unicode=True, width=88)
    )
    logger.info(
        "Harvested %d FAQ answers into %s", len(rows), settings.HARVESTED_FAQ_PATH
    )

    return len(rows)


def _from_page(page: Page) -> list[Harvested]:
    return [
        item
        for section in _faq_sections(page.body)
        for item in _pairs(section, source=page.url)
    ]


def _faq_sections(markdown: str) -> list[str]:
    """The body under every "Frequently Asked Questions" heading.

    A section ends at the next heading of the same or a shallower level, so a
    question written as a sub-heading stays inside its section.
    """
    matches = list(HEADING.finditer(markdown))
    sections = []

    for index, match in enumerate(matches):
        if not FAQ_HEADING.search(match.group(2)):
            continue

        depth = len(match.group(1))
        end = _section_end(markdown, matches[index + 1 :], depth)
        sections.append(markdown[match.end() : end])

    return sections


def _section_end(markdown: str, rest: list[re.Match[str]], depth: int) -> int:
    for later in rest:
        if len(later.group(1)) <= depth:
            return later.start()

    return len(markdown)


def _pairs(section: str, source: str) -> list[Harvested]:
    """Read a section as question then answer, however it was marked up.

    Some pages put each question in a sub-heading and some leave it as a bare
    paragraph, so both are flattened to the same list of blocks first and the
    question mark decides which is which.
    """
    blocks = [
        NUMBERING.sub("", block.strip())
        for block in HEADING.sub(r"\2\n", section).split("\n\n")
        if block.strip()
    ]

    found: list[Harvested] = []
    question = ""

    for block in blocks:
        if block.endswith("?"):
            question = block
            continue

        if question and MIN_ANSWER_CHARS <= len(block) <= MAX_ANSWER_CHARS:
            found.append(Harvested(question=question, answer=block, source=source))

        question = ""

    return found


def _deduplicated(found: list[Harvested]) -> list[Harvested]:
    """One answer per question, keeping the first page that answered it.

    The same question is templated across several centre pages, and a second
    row would only add a duplicate vector to compare against.
    """
    seen: dict[str, Harvested] = {}

    for item in found:
        seen.setdefault(item.question.casefold(), item)

    return sorted(seen.values(), key=lambda item: item.question)
