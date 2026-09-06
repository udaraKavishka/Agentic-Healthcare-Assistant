import pytest

from assistant.database.connection import fetch
from assistant.tools.sql_templates import (
    find_doctors,
    find_health_packages,
    find_lab_tests,
    get_schedule,
    list_specialties,
)

pytestmark = pytest.mark.usefixtures("hospital_db")


def test_doctors_come_back_with_their_specialty():
    doctors = find_doctors()

    assert len(doctors) == 11
    assert all(doctor["specialty"] for doctor in doctors)


def test_doctors_can_be_filtered_by_specialty_and_fee():
    affordable = find_doctors(specialty="Cardio", max_fee=4000)

    assert affordable
    assert all(doctor["consultation_fee"] <= 4000 for doctor in affordable)
    assert all("Cardio" in doctor["specialty"] for doctor in affordable)


def test_a_daily_clinic_appears_on_a_named_weekday():
    """Stored as day_of_week = 'Daily', so `= :day` would drop it silently."""
    daily = fetch(
        "SELECT d.name FROM channeling_sessions c JOIN doctors d ON d.id = c.doctor_id"
        " WHERE c.day_of_week = 'Daily' LIMIT 1"
    )
    doctor = daily[0]["name"]

    days = {row["day_of_week"] for row in get_schedule(doctor, day="Monday")}

    assert "Daily" in days


def test_a_name_still_matches_when_punctuation_differs():
    stored = fetch("SELECT name FROM doctors LIMIT 1")[0]["name"]
    typed = stored.replace(".", "")

    assert get_schedule(typed) or get_schedule(stored) == []


def test_an_unknown_doctor_returns_nothing():
    assert get_schedule("Dr Nobody At All") == []


def test_a_package_is_found_by_what_it_contains():
    """included_tests_and_services is prose in a governed row, not a document."""
    packages = find_health_packages("Pap smear")

    assert packages
    assert all(
        "pap smear" in package["included_tests_and_services"].lower()
        or "pap smear" in package["package_name"].lower()
        for package in packages
    )


def test_a_lab_test_is_found_by_its_code():
    by_code = find_lab_tests("LAB")

    assert by_code
    assert all(test["test_code"].startswith("LAB") for test in by_code)


def test_a_test_is_found_when_its_words_are_not_contiguous():
    """The row reads "Advanced Lipid & ApoB Profile"; the patient types two words."""
    tests = find_lab_tests("lipid profile")

    assert "Lipid" in tests[0]["test_name"]


def test_the_row_matching_the_most_words_comes_first():
    """Any word matches, so "Full Thyroid Profile" comes back for "profile" too.

    Which is the point: ranking, not filtering, is what stops an exact match
    from hiding a row the patient meant. The closest row still leads.
    """
    tests = find_lab_tests("lipid profile")

    assert len(tests) > 1
    assert "Thyroid" in tests[-1]["test_name"]


def test_a_near_miss_is_not_hidden_by_an_exact_match():
    """ "Women over 40" matches one package exactly and another only on the number.

    Requiring every word returns the exact one alone and never reaches
    "Females 40 years and above", which is the package that was asked for.
    """
    audiences = [
        row["target_audience"] for row in find_health_packages("women over 40")
    ]

    assert "Women over 40 or high risk" == audiences[0]
    assert "Females 40 years and above" in audiences


def test_word_order_does_not_matter():
    assert find_lab_tests("profile lipid") == find_lab_tests("lipid profile")


def test_a_phrase_matching_nothing_returns_nothing():
    assert find_lab_tests("helicopter maintenance") == []


def test_an_omitted_query_lists_everything():
    """A catalogue question reaches the tool with no query at all.

    The tool description tells the model to omit it, so the template never has
    to guess which words of a sentence were meant to filter.
    """
    assert len(find_health_packages()) == 11
    assert len(find_lab_tests()) == 17


def test_a_specific_term_still_narrows():
    assert len(find_health_packages("Pap smear")) == 3
    assert len(find_lab_tests("dengue")) == 1


def test_a_day_on_its_own_finds_whoever_is_working():
    """ "Which doctor works on Sunday?" names no doctor.

    The template used to require one, so the model had nothing to call and
    answered from the list of doctors instead of the timetable.
    """
    sessions = get_schedule(day="Sunday")
    working = {session["doctor"] for session in sessions}

    assert working == {"Prof. Arjuna De Silva", "Dr. Duminda Pathirana"}


def test_a_query_widens_rather_than_coming_back_empty():
    """No package is named "women over 40"; two are meant by it.

    Requiring every word finds nothing, and nothing reads to the patient as
    "we do not offer that", so the search falls back to any word.
    """
    names = [row["package_name"] for row in find_health_packages("women screening 40")]

    assert "Executive Female Screening (Above 40)" in names


def test_widening_does_not_invent_a_match():
    assert find_lab_tests("helicopter maintenance") == []


def test_a_speciality_is_found_by_the_word_the_patient_uses():
    """The column says Cardiology; the patient says cardiologist.

    Leaving this to the model meant the answer depended on whether it happened
    to normalise the word, so the most obvious question in the system was a
    coin flip.
    """
    for asked, expected in [
        ("cardiologist", "Cardiology"),
        ("neurosurgeon", "Neurosurgery"),
        ("paediatrician", "Paediatrics"),
        ("radiologist", "Radiology"),
    ]:
        found = find_doctors(asked)

        assert found, asked
        assert expected in found[0]["specialty"]


def test_an_exact_speciality_keeps_its_precision():
    """The stem pass is a fallback, not a widening: it runs only on no rows."""
    assert all("Cardiology" == row["specialty"] for row in find_doctors("Cardiology"))


def test_a_speciality_the_hospital_does_not_staff_finds_nothing():
    """Matching more loosely must not start inventing consultants."""
    assert find_doctors("ophthalmologist") == []


def test_every_staffed_speciality_is_listed_once():
    specialties = list_specialties()
    names = [row["specialty"] for row in specialties]

    assert len(names) == len(set(names))
    assert all(row["department"] for row in specialties)
    assert "Cardiology" in names
