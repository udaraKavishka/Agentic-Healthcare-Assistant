import pytest
import yaml

from assistant.config import settings
from assistant.nodes.faq import Entry, lookup

FAQ_QUESTIONS = [
    "hello",
    "hi",
    "good morning",
    "thanks",
    "what can you do",
    "contact number",
    "how do I channel a doctor",
    "are you a doctor",
]

HOSPITAL_QUESTIONS = [
    "What services does the hospital provide?",
    "Where are you located?",
    "What doctors are available and what do they charge?",
    "What health checkup packages do you offer?",
    "Do you have a heart centre?",
    "When does Dr Perera channel?",
    "Which package includes a Pap smear?",
    "I have chest pain, what should I take?",
]


def test_the_curated_faq_ships_with_the_repository():
    """Without the file every lookup returns None and the fast path is silently
    off, so this fails once and by name rather than in every match test."""
    assert settings.FAQ_PATH.exists(), f"no FAQ at {settings.FAQ_PATH}"

    entries = yaml.safe_load(settings.FAQ_PATH.read_text())

    assert entries, "the FAQ is empty"
    assert all({"question", "answer"} <= set(entry) for entry in entries)


@pytest.mark.parametrize("question", FAQ_QUESTIONS)
def test_a_common_enquiry_is_answered_without_a_model(question: str):
    assert lookup(question)


@pytest.mark.parametrize("question", HOSPITAL_QUESTIONS)
def test_a_question_about_the_hospital_is_left_to_the_router(question: str):
    """The bar is set for near-duplicates.

    A hospital question reaches 0.78 against curated wording, so a looser gate
    would answer "where are you located?" with a greeting instead of the page
    that has the address.
    """
    assert lookup(question) is None


def test_every_phrasing_reaches_the_same_answer():
    entry = Entry(question="Hello", answer="Hi there.", asked_as=("hi", "hey"))

    assert entry.phrasings == ("Hello", "hi", "hey")


def test_the_harvested_faq_ships_with_the_repository():
    """`make index` writes it from the corpus, so it can be absent locally and
    the fast path then silently shrinks to the curated entries alone."""
    assert settings.HARVESTED_FAQ_PATH.exists(), (
        f"no harvested FAQ at {settings.HARVESTED_FAQ_PATH}; run `make index`"
    )

    entries = yaml.safe_load(settings.HARVESTED_FAQ_PATH.read_text())

    assert entries
    assert all({"question", "answer", "source"} <= set(entry) for entry in entries)


def test_a_question_the_website_answers_is_matched_with_its_page():
    answer = lookup("Where is Nawaloka Hospital located?")

    assert answer is not None
    assert "nawaloka.com" in answer.citation
