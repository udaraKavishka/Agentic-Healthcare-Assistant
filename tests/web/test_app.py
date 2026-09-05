from web.app import Turn, _label, _prose


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
