import re
from typing import Any

from assistant.database.connection import fetch
from assistant.state import Passage

TITLES = {"dr", "prof", "mr", "mrs", "ms"}
WORD = re.compile(r"[a-z]+", re.IGNORECASE)

# Arguments are bound parameters, so this path never generates SQL and never
# needs the guard. The awkward parts of the schema are correct by construction
# here rather than by a model remembering them.


STEM = 6

DOCTORS = """
    SELECT d.name, d.qualifications, d.consultation_fee,
           s.name AS specialty, s.department
    FROM doctors d
    JOIN specialties s ON s.id = d.specialty_id
    {where}
    ORDER BY d.consultation_fee
"""


def find_doctors(
    specialty: str | None = None, max_fee: float | None = None
) -> list[dict[str, Any]]:
    """Doctors, narrowed by speciality or by fee.

    The speciality is matched whole first and by stem only if that found
    nothing, so an exact request keeps its precision and an inflected one still
    lands.
    """
    fee, params = _fee_clause(max_fee)

    if not specialty:
        return _doctors(fee, params)

    whole = _doctors(
        fee + ["s.name LIKE :specialty"], params | {"specialty": f"%{specialty}%"}
    )

    return whole or _doctors(*_stemmed(specialty, fee, params))


def list_specialties() -> list[dict[str, Any]]:
    """Every speciality the hospital staffs, for when the asked-for one is absent.

    "We do not have that" is a poor answer on its own when the next question is
    always "then what do you have".
    """
    return fetch(
        """
        SELECT DISTINCT s.name AS specialty, s.department
        FROM specialties s
        JOIN doctors d ON d.specialty_id = s.id
        ORDER BY s.name
        """
    )


def _doctors(clauses: list[str], params: dict[str, Any]) -> list[dict[str, Any]]:
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    return fetch(DOCTORS.format(where=where), params)


def _fee_clause(max_fee: float | None) -> tuple[list[str], dict[str, Any]]:
    if max_fee is None:
        return [], {}

    return ["d.consultation_fee <= :max_fee"], {"max_fee": max_fee}


def _stemmed(
    specialty: str, fee: list[str], params: dict[str, Any]
) -> tuple[list[str], dict[str, Any]]:
    """Match the root of each word against the speciality or its department."""
    stems = {
        word[:STEM].lower() for word in WORD.findall(specialty) if len(word) >= STEM
    }

    if not stems:
        return fee + ["1 = 0"], params

    clauses = []
    stemmed = dict(params)

    for index, stem in enumerate(sorted(stems)):
        key = f"stem{index}"
        stemmed[key] = f"%{stem}%"
        clauses.append(f"(s.name LIKE :{key} OR s.department LIKE :{key})")

    return fee + clauses, stemmed


def get_schedule(doctor_name: str = "", day: str = "") -> list[dict[str, Any]]:
    """Channeling sessions, narrowed by doctor or by day or by both.

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
    return _search(
        query,
        columns=("test_name", "test_code", "category", "preparation_instructions"),
        statement="""
        SELECT test_code, test_name, category, price, fasting_required_hours,
               preparation_instructions, report_delivery_hours
        FROM lab_tests
        WHERE {where}
        ORDER BY price
        """,
    )


def find_health_packages(query: str = "") -> list[dict[str, Any]]:
    """Packages by name, category, audience, or what they include.

    included_tests_and_services is free prose inside the relational store, so
    "which package includes a Pap smear?" is answered here with LIKE. It reads
    like an unstructured question but the answer lives in a governed row.
    """
    return _search(
        query,
        columns=(
            "package_name",
            "category",
            "target_audience",
            "included_tests_and_services",
        ),
        statement="""
        SELECT package_name, category, price, target_audience,
               included_tests_and_services
        FROM health_packages
        WHERE {where}
        ORDER BY price
        """,
    )


def _search(
    query: str, columns: tuple[str, ...], statement: str
) -> list[dict[str, Any]]:
    """Any word matches, and the rows that matched the most come first.

    Requiring every word is the precise reading and it hides rows the patient
    meant: "women over 40" matches "Women over 40 or high risk" on all three
    words, so an exact-match search stops there and never reaches "Females 40
    years and above", which is the package that was asked for.

    Matching any word finds both and ranking by how many words matched puts the
    closest first. The catalogues are tens of rows, so the cost of the near
    misses that come with them is a longer prompt, not a worse answer.
    """
    where, params = _clauses(query, columns)
    rows = fetch(statement.format(where=where), params)
    words = _words(query)

    # Stable, so rows that matched equally well keep the statement's own order.
    return sorted(rows, key=lambda row: -_matched(row, words))


def _clauses(query: str, columns: tuple[str, ...]) -> tuple[str, dict[str, Any]]:
    """Match word by word, in any of the columns, in any order.

    A single LIKE over the whole phrase matches only contiguous text: "lipid
    profile" misses "Advanced Lipid & ApoB Profile", which is the row the
    patient meant.
    """
    words = _words(query)

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

    return " OR ".join(clauses), params


def _words(query: str) -> list[str]:
    return [word.lower() for word in WORD.findall(query)]


def _matched(row: dict[str, Any], words: list[str]) -> int:
    """How much of the query this row accounts for, counted once per word."""
    haystack = " ".join(str(value) for value in row.values()).lower()

    return sum(word in haystack for word in words)


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
