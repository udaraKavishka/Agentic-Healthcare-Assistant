# Agentic Healthcare Assistant

A hybrid agentic chatbot for Nawaloka Hospitals. Hospital knowledge is split
across two very different stores, and a patient asking a question should not
have to know which one holds their answer:

- **Unstructured** — services, clinical centres and general policies, scraped
  from the hospital website and held in a vector database.
- **Structured** — doctors, specialities, channeling schedules, lab test prices
  and health packages, held in a relational database.

The agent decides per question whether to search the vector store, query the
database, or combine both, and answers over a streaming chat UI.


## Stack

| Concern | Choice |
|---|---|
| API | FastAPI |
| Chat UI | Streamlit |
| Models | Groq — `gpt-oss-20b` routes, `gpt-oss-120b` answers |
| Vector store | Qdrant, embedded |
| Relational store | SQLite, opened read-only |
| Packaging | uv |

The reasoning behind each of these, and the alternatives rejected, is in
`docs/ARCHITECTURE.md`.

## Requirements

- Python 3.12 — pinned in `.python-version`, fetched by uv
- [uv](https://docs.astral.sh/uv/)
- A Groq API key — free tier, no billing: <https://console.groq.com/keys>

## Setup

```bash
make install          # uv sync
cp .env.example .env  # then fill in GROQ_API_KEY
```

## Run

```bash
make run              # http://localhost:8000
```

- `GET /health` — liveness
- `/docs` — OpenAPI, served everywhere except production

## Quality gate

```bash
make check            # ruff, ruff format, pyright, pytest
```

`requirements.txt` and `requirements-dev.txt` are exported from `uv.lock` by a
pre-commit hook, so they cannot drift from what is actually installed. Install
the hooks once with `uv run pre-commit install`.

