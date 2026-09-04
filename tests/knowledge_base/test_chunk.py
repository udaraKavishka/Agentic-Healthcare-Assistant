from assistant.knowledge_base.chunk import MAX_CHARS, chunk_page

MARKDOWN = """An introduction that arrives before any heading, long enough to survive the
minimum length filter and be kept as a chunk of its own.

# Heart Centre

Cardiology services around the clock, staffed by resident consultants every
day of the week, with an intensive care unit attached to the ward.

## Consultants

Dr Perera and Dr Silva channel here on weekdays, and the unit runs a walk-in
clinic on Saturday mornings for follow-up patients.
"""


def test_each_heading_becomes_its_own_chunk():
    chunks = chunk_page(MARKDOWN, url="https://example.test/heart", title="Heart")

    assert [chunk.heading for chunk in chunks] == ["", "Heart Centre", "Consultants"]


def test_source_travels_with_every_chunk():
    chunks = chunk_page(MARKDOWN, url="https://example.test/heart", title="Heart")

    assert all(chunk.url == "https://example.test/heart" for chunk in chunks)
    assert all(chunk.title == "Heart" for chunk in chunks)


def test_short_fragments_are_dropped():
    chunks = chunk_page("# Empty\n\nToo short.\n", url="u", title="t")

    assert chunks == []


def test_a_long_section_is_split_on_paragraph_boundaries():
    paragraph = "Nawaloka runs a full diagnostic laboratory service. " * 12
    body = f"# Laboratory\n\n{paragraph}\n\n{paragraph}\n\n{paragraph}"

    chunks = chunk_page(body, url="u", title="t")

    assert len(chunks) > 1
    assert all(len(chunk.text) <= MAX_CHARS for chunk in chunks)
