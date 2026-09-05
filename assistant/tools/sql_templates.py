import re
from typing import Any

from assistant.database.connection import fetch

TITLES = {"dr", "prof", "mr", "mrs", "ms"}
WORD = re.compile(r"[a-z]+", re.IGNORECASE)

# Arguments are bound parameters, so this path never generates SQL and never
# needs the guard. The awkward parts of the schema are correct by construction
# here rather than by a model remembering them.


def find_doctors(
    specialty: str | None = None, max_fee: float | None = None
) -> list[dict[str, Any]]:
    clauses = []
    params: dict[str, Any] = {}

    if specialty:
        clauses.append("s.name LIKE :specialty")
        params["specialty"] = f"%{specialty}%"

    if max_fee is not None:
        clauses.append("d.consultation_fee <= :max_fee")
        params["max_fee"] = max_fee

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    return fetch(
        f"""
        SELECT d.name, d.qualifications, d.consultation_fee,
               s.name AS specialty, s.department
        FROM doctors d
        JOIN specialties s ON s.id = d.specialty_id
        {where}
        ORDER BY d.consultation_fee
        """,
        params,
    )


def get_schedule(doctor_name: str, day: str | None = None) -> list[dict[str, Any]]:
    """Channeling sessions for a doctor, optionally on one day.

    A daily clinic is stored as day_of_week = 'Daily', not as seven weekday
    rows. Filtering with `= :day` silently drops it, producing a wrong answer
    with no error, which is why the day filter lives here and not in a prompt.
    """
    name_filter, params = _name_match(doctor_name)
    day_filter = ""

    if day:
        day_filter = "AND c.day_of_week IN (:day, 'Daily')"
        params["day"] = day.capitalize()

    return fetch(
        f"""
        SELECT d.name AS doctor, c.day_of_week, c.start_time, c.end_time,
               c.room_number, c.max_patients, d.consultation_fee
        FROM channeling_sessions c
        JOIN doctors d ON d.id = c.doctor_id
        WHERE {name_filter} {day_filter}
        ORDER BY c.day_of_week, c.start_time
        """,
        params,
    )


def find_lab_tests(query: str) -> list[dict[str, Any]]:
    return fetch(
        """
        SELECT test_code, test_name, category, price, fasting_required_hours,
               preparation_instructions, report_delivery_hours
        FROM lab_tests
        WHERE test_name LIKE :query OR test_code LIKE :query
              OR category LIKE :query OR preparation_instructions LIKE :query
        ORDER BY price
        """,
        {"query": f"%{query}%"},
    )


def find_health_packages(query: str) -> list[dict[str, Any]]:
    """Packages by name, category, audience, or what they include.

    included_tests_and_services is free prose inside the relational store, so
    "which package includes a Pap smear?" is answered here with LIKE. It reads
    like an unstructured question but the answer lives in a governed row.
    """
    return fetch(
        """
        SELECT package_name, category, price, target_audience,
               included_tests_and_services
        FROM health_packages
        WHERE package_name LIKE :query OR category LIKE :query
              OR target_audience LIKE :query
              OR included_tests_and_services LIKE :query
        ORDER BY price
        """,
        {"query": f"%{query}%"},
    )


def _name_match(doctor_name: str) -> tuple[str, dict[str, Any]]:
    """Match a name a word at a time, ignoring titles and punctuation.

    The database stores "Dr. Duminda Pathirana"; a patient types "Dr Duminda
    Pathirana". A single LIKE over the whole string misses on the full stop and
    returns nothing, which reads as "this doctor has no clinics".
    """
    words = [word for word in WORD.findall(doctor_name) if word.lower() not in TITLES]

    if not words:
        return "1 = 1", {}

    params = {f"name{index}": f"%{word}%" for index, word in enumerate(words)}
    clauses = " AND ".join(f"d.name LIKE :{key}" for key in params)

    return clauses, params
