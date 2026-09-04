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

## Build the knowledge base

```bash
make scrape           # render the website into knowledge/scraped/
make index            # embed the corpus into the vector store
```

`make scrape` drives a headless browser: the hospital site is a client-side
React application, so a plain HTTP fetch returns an empty shell. It reads
`robots.txt`, walks the sitemap, waits for each page to render, and keeps only
the `<main>` content so navigation and footers stay out of the corpus. One
request per second.

The corpus is committed, so a reviewer never has to re-crawl the site — run
`make scrape` only to refresh it. The current crawl holds 14 of the 30 sitemap
pages; the rest rendered too little text or timed out and are logged by
`make scrape`.

Do not run `make index` while the API is up: the vector store is embedded and
single-process.

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
