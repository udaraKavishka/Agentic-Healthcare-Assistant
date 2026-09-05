import pytest

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
