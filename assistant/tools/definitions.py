# Descriptions the router reads when choosing a query. Tool-selection accuracy
# tracks the quality of these more than anything in the code, so they name the
# columns behind each tool and the questions each one answers.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "find_doctors",
            "description": (
                "Doctors, their speciality, qualifications and consultation fee."
                " Use for who practises what, and what a consultation costs."
                " Omit both arguments to list every doctor."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "specialty": {
                        "type": "string",
                        "description": "Speciality name or part of one, e.g. Cardio",
                    },
                    "max_fee": {
                        "type": "number",
                        "description": "Highest consultation fee in rupees",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_schedule",
            "description": (
                "Channeling sessions for one doctor: day, start and end time,"
                " room and fee. Use for when a named doctor is available."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_name": {
                        "type": "string",
                        "description": "The doctor's name as the patient gave it",
                    },
                    "day": {
                        "type": "string",
                        "description": "A weekday name, if the question names one",
                    },
                },
                "required": ["doctor_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_lab_tests",
            "description": (
                "Lab tests: code, name, category, price, fasting hours,"
                " preparation instructions and report turnaround. Search by the"
                " name of the test, not by a word from the question — for"
                " 'do I need to fast before a lipid profile' pass 'lipid profile'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Test name, code or category",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_health_packages",
            "description": (
                "Health packages: name, category, price, who they are for, and"
                " the full list of tests each includes. The contents are stored"
                " as prose, so search by the thing being looked for — for"
                " 'which package includes a Pap smear' pass 'Pap smear'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "A package name, audience, or a test it should include"
                        ),
                    }
                },
                "required": ["query"],
            },
        },
    },
]
