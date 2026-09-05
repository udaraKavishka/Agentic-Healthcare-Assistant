import pytest

from assistant.database.connection import fetch
from assistant.tools.sql_templates import (
    find_doctors,
    find_health_packages,
    find_lab_tests,
    get_schedule,
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
