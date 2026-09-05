<div align="center">

<img src="web/assets/logo.svg" width="96" alt="Agentic Healthcare Assistant">

# Agentic Healthcare Assistant

**Dynamically routing user queries between scraped web knowledge (Vector Database)<br>and structured database queries (SQL Database) to deliver accurate, context-aware responses through a chat UI.**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-SSE-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)
[![Groq](https://img.shields.io/badge/Groq-gpt--oss-F55036?logo=groq&logoColor=white)](https://groq.com)
[![Qdrant](https://img.shields.io/badge/Qdrant-hybrid%20search-DC244C?logo=qdrant&logoColor=white)](https://qdrant.tech)

</div>

---

A hybrid agentic chatbot for **Nawaloka Hospitals**. Hospital knowledge is split
across two very different stores, and a patient should not have to know which
one holds their answer:

- **Unstructured**: services, clinical centres, rooms and policies, scraped
  from the hospital website into a vector database.
- **Structured**: doctors, specialities, channeling schedules, lab test prices
  and health packages, in a relational database.

The agent decides, per question, which to use.

```
patient question
      ↓
  route          gpt-oss-20b: rewrite the follow-up, pick one of five routes
      ↓
  retrieve       sql tools · hybrid vector search · both, concurrently
      ↓
  answer         gpt-oss-120b, grounded in what was retrieved, or abstain
```

## Results

| | |
|---|---|
| Routing accuracy | **29/29** |
| Retrieval hit rate | **21/22** in the top 5, mean reciprocal rank 0.93 |
| SQL execution accuracy | **16/16**, checked against the rows, not the route |
| FAQ fast path | 51 ms median, no model call |
| Corpus | 82 documents, 834 chunks, from 89 URLs |
| Database | 10 specialities, 11 doctors, 15 sessions, 17 lab tests, 11 packages |
| Tests | 113, with `ruff`, `ruff format` and `pyright` clean |

The three scores come from `make evaluate`.

## Stack

| Concern | Choice |
|---|---|
| API | FastAPI, server-sent events |
| Chat UI | Streamlit |
| Models | Groq: `gpt-oss-20b` routes, `gpt-oss-120b` answers |
| Vector store | Qdrant, embedded, dense + BM25 fused by RRF, then reranked |
| Embeddings | fastembed ONNX |
| Relational store | SQLite, opened read-only |
| Packaging | uv |


## Setup

You need [uv](https://docs.astral.sh/uv/) and a free
[Groq API key](https://console.groq.com/keys). Python 3.12 is pinned in
`.python-version`; uv fetches it.

```bash
git clone https://github.com/udaraKavishka/Agentic-Healthcare-Assistant.git
cd Agentic-Healthcare-Assistant

make install                # creates .venv, installs from the lockfile
cp .env.example .env        # paste your key into GROQ_API_KEY

make seed                   # data.sql -> knowledge/hospital.db
make index                  # committed corpus -> vector store
```

Never activate anything: every command goes through `uv run`, which uses `.venv`
itself. The first `make index` downloads about 130 MB of ONNX weights; later
runs re-embed only chunks whose text changed.

## Running it

Two processes. Any one of these:

```bash
make dev                    # both, one terminal
make tmux                   # both, in a tmux session named `assistant`
make run                    # API only, on :8000
make ui                     # UI only, on :8501
```

Then open <http://localhost:8501>. The API serves `/docs` and `GET /health`.

Under tmux: `Ctrl-b d` detaches, `tmux attach -t assistant` returns,
`tmux kill-session -t assistant` stops everything.

The vector store is embedded and single-process, so **stop the API before
`make index`**. The command says so if you forget.

## Evaluating

```bash
make evaluate               # routing, retrieval, SQL execution
```

Three scores, because they fail independently: routing can be right while
retrieval returns the wrong page, and both can be right while a query filters on
the wrong argument. Each golden set is weighted towards what breaks: prose
columns that live in SQL, the `'Daily'` clinic, dual-source questions, clinical
refusals.

Retrieval runs entirely locally, so it needs the vector store built and the API
stopped. Routing and SQL execution call the model.

## Refreshing the corpus

```bash
make scrape                 # render the website into knowledge/scraped/
make index
```

`knowledge/scraped/` is committed, so a reviewer never has to re-crawl the
hospital's site. `make index` also rewrites `knowledge/faq.harvested.yml` from
the FAQ sections the site publishes, so the fast path refreshes with the site
rather than being hand-maintained.

The site is a client-side React application, so the crawler drives a headless
browser. It seeds from the sitemap but follows links, because the sitemap is
stale: it advertises pages that no longer render and omits live ones.

## Quality gate

```bash
make check                  # ruff, ruff format, pyright, pytest
```

`requirements.txt` and `requirements-dev.txt` are exported from `uv.lock` by a
pre-commit hook, so they cannot drift. Install the hooks once with
`uv run pre-commit install`.

## Layout

```
assistant/
  api/             FastAPI app, routes, SSE encoder
  database/        data.sql loader, read-only connection, SQL guard
  knowledge_base/  chunking, embeddings, Qdrant store, hybrid search
  llm/             Groq client, rate-limit budget
  memory/          conversation store
  nodes/           faq, route, retrieve_sql, retrieve_vector, synthesize
  scrape/          robots, sitemap, headless crawl, PDF text
  tools/           typed SQL queries and their tool schemas
  evaluate/        the three scores
  pipeline.py      one turn, top to bottom
web/               Streamlit chat UI
configs/           prompts.yml, every word the models are given
evals/             the three golden sets
knowledge/         data.sql, the committed corpus, the FAQ files
```

## Safety

The agent cannot write to the hospital database and cannot reach outside its
five tables. Four independent walls: the connection is opened read-only at the
driver, `PRAGMA query_only` is set, generated SQL is validated against the parse
tree with a table allowlist, and every query carries a row limit and a deadline.

Clinical questions are a routing decision, not a prompt instruction: they
short-circuit to a fixed referral before the answer model is called.

## Troubleshooting

**"The assistant is busy."** The free tier allows 30 requests and 8,000 tokens a
minute. The limiter waits for headroom and, past 20 seconds, says so rather than
hanging.

**"The vector store is already open."** The API is holding it. Stop it, then
`make index`.

## Author

**Udara Nalawansa**

[udaradev.me](https://udaradev.me) ·
[github.com/udaraKavishka](https://github.com/udaraKavishka) ·
[hello@udaradev.me](mailto:hello@udaradev.me)
