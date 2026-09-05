import re
from typing import Any

from assistant.database.connection import fetch
from assistant.state import Passage

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


def find_lab_tests(query: str = "") -> list[dict[str, Any]]:
    columns = (
        "test_name",
        "test_code",
        "category",
        "preparation_instructions",
    )
    where, params = _all_words(query, columns)

    return fetch(
        f"""
        SELECT test_code, test_name, category, price, fasting_required_hours,
               preparation_instructions, report_delivery_hours
        FROM lab_tests
        WHERE {where}
        ORDER BY price
        """,
        params,
    )


def find_health_packages(query: str = "") -> list[dict[str, Any]]:
    """Packages by name, category, audience, or what they include.

    included_tests_and_services is free prose inside the relational store, so
    "which package includes a Pap smear?" is answered here with LIKE. It reads
    like an unstructured question but the answer lives in a governed row.
    """
    columns = (
        "package_name",
        "category",
        "target_audience",
        "included_tests_and_services",
    )
    where, params = _all_words(query, columns)

    return fetch(
        f"""
        SELECT package_name, category, price, target_audience,
               included_tests_and_services
        FROM health_packages
        WHERE {where}
        ORDER BY price
        """,
        params,
    )


def _all_words(query: str, columns: tuple[str, ...]) -> tuple[str, dict[str, Any]]:
    """Require every word, in any of the columns, in any order.

    A single LIKE over the whole phrase matches only contiguous text: "lipid
    profile" misses "Advanced Lipid & ApoB Profile", which is the row the
    patient meant.
    """
    words = WORD.findall(query)

    if not words:
        return "1 = 1", {}

    params: dict[str, Any] = {}
    clauses = []

    for index, word in enumerate(words):
        key = f"word{index}"
        params[key] = f"%{word}%"
        clauses.append(
            "(" + " OR ".join(f"{column} LIKE :{key}" for column in columns) + ")"
        )

    return " AND ".join(clauses), params


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


def to_passages(rows: list[dict[str, Any]], citation: str) -> list[Passage]:
    return [
        Passage(origin="sql", content=_render(row), citation=citation) for row in rows
    ]


def _render(row: dict[str, Any]) -> str:
    # Key-value rather than CSV: repeating the column beside each value stops
    # the model misaligning columns when it reads the rows back.
    return "\n".join(
        f"{key}: {value}" for key, value in row.items() if value is not None
    )
