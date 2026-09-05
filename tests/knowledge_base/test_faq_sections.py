from assistant.knowledge_base.corpus import Page
from assistant.knowledge_base.faq_sections import _from_page

HEADINGS = Page(
    url="/channeling",
    title="Channeling",
    body="""## FAQs - Channeling & Doctor Booking

### 1. Can I book a doctor appointment on the same day?

Yes. Same-day doctor booking is available for selected specialists, subject
to availability.

### 2. What information is needed for doctor booking?

Basic patient details, preferred specialist, and appointment date are usually
sufficient.

## Book Appointment Now

Call us on 0115 577 111 to reserve a slot with any consultant on the list.
""",
)

PARAGRAPHS = Page(
    url="/heart-centre",
    title="Heart Centre",
    body="""## Frequently Asked Questions

Do I need heart surgery for every heart condition?

No. Many conditions are managed with medication or minimally invasive
procedures. Surgery is recommended only when clinically necessary.
""",
)


def test_questions_written_as_sub_headings_are_read_as_questions():
    found = _from_page(HEADINGS)

    assert [item.question for item in found] == [
        "Can I book a doctor appointment on the same day?",
        "What information is needed for doctor booking?",
    ]


def test_questions_left_as_paragraphs_are_read_the_same_way():
    found = _from_page(PARAGRAPHS)

    assert len(found) == 1
    assert found[0].answer.startswith("No. Many conditions")
    assert found[0].source == "/heart-centre"


def test_the_section_ends_at_the_next_heading_of_the_same_level():
    """Everything after the FAQ heading is not part of the FAQ.

    Without the depth check the call to action below would be harvested as an
    answer to the question above it.
    """
    answers = [item.answer for item in _from_page(HEADINGS)]

    assert not any("0115 577 111" in answer for answer in answers)


def test_a_page_with_no_faq_section_contributes_nothing():
    assert _from_page(Page(url="/u", title="t", body="## Awards\n\nWe won.")) == []
