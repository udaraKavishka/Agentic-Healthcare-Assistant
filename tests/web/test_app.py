from web.app import BACKLOG, Turn, _label, _prose, _type


def test_a_separator_dash_becomes_the_colon_it_means():
    """The model writes a dash between a name and its detail whatever the prompt says."""
    assert _prose("**Heart Centre** – offers cardiac care") == (
        "**Heart Centre**: offers cardiac care"
    )


def test_an_em_dash_is_treated_the_same():
    assert _prose("Dr. Perera — Rs 4,000") == "Dr. Perera: Rs 4,000"


def test_a_hyphen_inside_a_word_is_left_alone():
    assert _prose("MD, DM (Cardiology), 24/7 walk-in clinic") == (
        "MD, DM (Cardiology), 24/7 walk-in clinic"
    )


def test_a_url_is_labelled_by_its_page():
    assert _label("https://www.nawaloka.com/heart-centre") == "heart centre"
    assert _label("https://www.nawaloka.com/health-checkups/") == "health checkups"


def test_a_url_with_no_path_falls_back_to_the_host():
    assert _label("https://www.nawaloka.com") == "www.nawaloka.com"


def test_a_turn_joins_the_tokens_it_collected():
    turn = Turn()
    turn.spoken.extend(["Yes, ", "we have ", "a heart centre."])

    assert turn.answer == "Yes, we have a heart centre."


def test_a_fresh_turn_has_no_answer():
    assert Turn().answer == ""


def test_typing_reveals_a_burst_a_few_characters_at_a_time():
    """A whole chunk rendered at once lands the reply in jumps, not as typing."""
    turn = Turn(pending="Heart Centre")
    frames: list[str] = []
    _type(_Recorder(frames), turn)

    assert turn.answer == "Heart Centre"
    assert len(frames) > 1
    assert frames[0] == "Hear"


def test_a_model_far_ahead_is_shown_at_once():
    """Past the backlog, pacing the reader would only make them wait."""
    turn = Turn(pending="x" * (BACKLOG + 50))
    frames: list[str] = []
    _type(_Recorder(frames), turn)

    assert frames == ["x" * (BACKLOG + 50)]


class _Recorder:
    """Stands in for the Streamlit placeholder, keeping every frame drawn."""

    def __init__(self, frames: list[str]) -> None:
        self._frames = frames

    def markdown(self, text: str) -> None:
        self._frames.append(text)
