from assistant.knowledge_base.corpus import _page, _split_front_matter

DOCUMENT = """---
url: https://www.nawaloka.com/laboratory
title: Laboratory
---

# Laboratory

Body text.
"""


def test_front_matter_is_split_back_out():
    url, title, body = _split_front_matter(DOCUMENT)

    assert url == "https://www.nawaloka.com/laboratory"
    assert title == "Laboratory"
    assert body.strip().startswith("# Laboratory")


def test_a_document_without_front_matter_is_all_body():
    assert _split_front_matter("# Laboratory\n") == ("", "", "# Laboratory\n")


def test_a_page_with_no_front_matter_falls_back_to_its_filename():
    page = _page("# Laboratory\n", fallback="www-nawaloka-com-laboratory")

    assert page.url == "www-nawaloka-com-laboratory"
    assert page.title == "www-nawaloka-com-laboratory"
