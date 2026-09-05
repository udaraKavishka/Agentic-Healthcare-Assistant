from assistant.knowledge_base.chunk import Chunk
from assistant.knowledge_base.index import _contextualised, _point_id


def test_a_chunk_carries_its_page_and_heading():
    chunk = Chunk(text="Body.", heading="Channeling", url="u", title="Heart Centre")

    assert _contextualised(chunk) == "Heart Centre — Channeling\n\nBody."


def test_a_chunk_before_the_first_heading_is_not_left_with_a_dangling_dash():
    chunk = Chunk(text="Body.", heading="", url="u", title="Heart Centre")

    assert _contextualised(chunk) == "Heart Centre\n\nBody."


def test_an_unchanged_chunk_keeps_its_id():
    chunk = Chunk(text="Body.", heading="Channeling", url="u", title="Heart")

    assert _point_id(chunk, "Heart — Channeling\n\nBody.") == _point_id(
        chunk, "Heart — Channeling\n\nBody."
    )


def test_editing_a_chunk_changes_its_id():
    chunk = Chunk(text="Body.", heading="Channeling", url="u", title="Heart")

    assert _point_id(chunk, "one") != _point_id(chunk, "two")


def test_the_same_text_on_two_pages_stays_two_points():
    first = Chunk(text="Call 0115 577 111.", heading="", url="/heart", title="Heart")
    second = Chunk(text="Call 0115 577 111.", heading="", url="/eye", title="Eye")

    assert _point_id(first, "shared") != _point_id(second, "shared")


def test_changing_the_embedding_model_invalidates_every_id(monkeypatch):
    chunk = Chunk(text="Body.", heading="", url="u", title="t")
    before = _point_id(chunk, "Body.")

    monkeypatch.setattr("assistant.knowledge_base.index.DENSE_MODEL", "other/model")

    assert _point_id(chunk, "Body.") != before
