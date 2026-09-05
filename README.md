# Agentic Healthcare Assistant

A hybrid agentic chatbot for Nawaloka Hospitals. Hospital knowledge is split
across two very different stores, and a patient asking a question should not
have to know which one holds their answer:

- **Unstructured** — services, clinical centres, rooms and policies, scraped
  from the hospital website into a vector database.
- **Structured** — doctors, specialities, channeling schedules, lab test prices
  and health packages, held in a relational database.

The agent decides, per question, whether to search the vector store, query the
database, or use both, and answers over a streaming chat UI.

Built for the Associate AI Engineer technical assignment.

```
patient question
      ↓
  route          gpt-oss-20b: rewrite the follow-up and pick one of five routes
      ↓
  retrieve       sql tools · hybrid vector search · both, concurrently
      ↓
  answer         gpt-oss-120b, grounded in what was retrieved, or abstain
```

## Results

| | |
|---|---|
| Routing accuracy | **29/29** on the golden set (`make evaluate`) |
| Corpus | 82 documents, 834 chunks, from 89 URLs crawled |
| Database | 10 specialities, 11 doctors, 15 sessions, 17 lab tests, 11 packages |
| Tests | 79, with `ruff`, `ruff format` and `pyright` clean |

## Stack

| Concern | Choice |
|---|---|
| API | FastAPI, server-sent events |
| Chat UI | Streamlit |
| Models | Groq: `gpt-oss-20b` routes, `gpt-oss-120b` answers |
| Vector store | Qdrant, embedded, dense + BM25 fused by RRF, then reranked |
| Embeddings | fastembed ONNX, so nothing pulls in PyTorch |
| Relational store | SQLite, opened read-only |
| Packaging | uv |

Every decision, and the alternatives rejected, is recorded in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). Each task has its own write-up
in [`docs/tasks/`](docs/tasks).

## Requirements

- Python 3.12 — pinned in `.python-version`, fetched by uv
- [uv](https://docs.astral.sh/uv/)
- A Groq API key — free tier, no billing: <https://console.groq.com/keys>

## Setup

```bash
make install                # uv sync
cp .env.example .env        # then fill in GROQ_API_KEY
make seed                   # data.sql -> knowledge/hospital.db
make index                  # committed corpus -> vector store
```

The first `make index` downloads about 130 MB of ONNX model weights and takes a
few minutes; later runs re-embed only chunks that changed.

## Run

Two processes, one command each:

```bash
make run                    # API on :8000
make ui                     # chat UI on :8501
```

`/docs` serves the OpenAPI schema outside production, and `GET /health` is the
liveness check.

## Refreshing the corpus

```bash
make scrape                 # render the website into knowledge/scraped/
make index
```

`knowledge/scraped/` is committed, so a reviewer never has to re-crawl the
hospital's site. Run `make scrape` only to refresh it.

The site is a client-side React application, so the crawler drives a headless
browser rather than fetching HTML. It seeds from the sitemap but follows links,
because the sitemap is stale: it advertises pages that no longer render and
omits live ones, including the health checkup packages.

Do not run `make index` while the API is up — the vector store is embedded and
single-process.

## Evaluating

```bash
make evaluate               # routing accuracy, as a confusion matrix
```

`evals/questions.yml` is weighted towards what breaks: prose columns that live
in SQL, the `'Daily'` clinic, questions needing both sources, and clinical
refusals. The matrix matters more than the score, because *which way* routing
fails decides whether a patient gets a wrong answer or none.

## Quality gate

```bash
make check                  # ruff, ruff format, pyright, pytest
```

`requirements.txt` and `requirements-dev.txt` are exported from `uv.lock` by a
pre-commit hook, so they cannot drift from what is installed. Install the hooks
once with `uv run pre-commit install`.

## Layout

```
assistant/
  api/          FastAPI app, routes, SSE encoder
  database/     data.sql loader, read-only connection, SQL guard
  knowledge_base/  chunking, embeddings, Qdrant store, hybrid search
  llm/          Groq client, rate-limit budget
  memory/       conversation store
  nodes/        route, retrieve_sql, retrieve_vector, synthesize
  scrape/       robots, sitemap, headless crawl, PDF text
  tools/        typed SQL queries and their tool schemas
  pipeline.py   one turn, top to bottom
web/            Streamlit chat UI
configs/        prompts.yml, every word the models are given
evals/          the golden question set
knowledge/      data.sql and the committed corpus
```

## Safety

The agent cannot write to the hospital database and cannot reach outside its
five tables. Four independent walls: the connection is opened read-only at the
driver, `PRAGMA query_only` is set, generated SQL is validated against the parse
tree with a table allowlist, and every query carries a row limit and a deadline.

Clinical questions are a routing decision, not a prompt instruction: they
short-circuit to a fixed referral before the answer model is ever called.

## Troubleshooting

**`uv` warns that `VIRTUAL_ENV` does not match the project environment.** A
stale shell variable from an earlier `source .venv/bin/activate`. uv ignores it
and uses `.venv`; clear it with `unset VIRTUAL_ENV` or a new shell.

**The assistant says it is busy.** The free tier allows 30 requests and 8,000
tokens a minute. The limiter waits for headroom and, past 20 seconds, says so
rather than hanging.
