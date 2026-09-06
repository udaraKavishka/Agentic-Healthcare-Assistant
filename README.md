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
one holds their answer. Services, clinical centres and policies live on the
website. Doctors, channeling schedules, lab prices and health packages live in a
relational database. The agent decides, per question, which to use.

## Contents

- [Architecture](#architecture)
- [Results](#results)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Evaluation](#evaluation)
- [Testing and quality gate](#testing-and-quality-gate)
- [Refreshing the corpus](#refreshing-the-corpus)
- [Project structure](#project-structure)
- [Safety](#safety)
- [Troubleshooting](#troubleshooting)
- [Author](#author)

## Architecture

```
patient question
   │
   ▼
FAQ gate           local embedding, no model call
   │ miss
   ▼
route              gpt-oss-20b, one call: rewrite the follow-up, pick a route
   │
   ├─ refuse ────▶ fixed referral to a doctor, no answer model
   │
   ▼
retrieve           sql tools, hybrid vector search, or both concurrently
   │
   ▼
answer             gpt-oss-120b, streamed, grounded in what was retrieved
   │
   ▼
remember           the turn and its route, in conversations.db
```

Five routes: `faq`, `vector`, `sql`, `both`, `refuse`. The router returns the
label directly rather than having it inferred from which tools were called, so
the decision is one thing and can be scored against a golden set.

| Layer | Role | Built with |
|---|---|---|
| API | `POST /chat` as server-sent events | FastAPI, uvicorn |
| Chat UI | Consumes the event stream, shows the route live | Streamlit |
| Models | `gpt-oss-20b` routes, `gpt-oss-120b` answers | Groq |
| Vector store | Dense and BM25 fused by RRF, then a cross-encoder rerank | Qdrant, embedded |
| Embeddings | Dense, sparse and rerank from one ONNX dependency | fastembed |
| Relational store | Opened read-only, behind four safety walls | SQLite, sqlglot |
| Memory | Verbatim turn window, in its own writable database | SQLite |
| Scraping | Headless render, since the site is a React application | Playwright |
| Packaging | Locked dependencies, pinned Python | uv |

Three offline commands fill three stores, none of them calling a model:

| Command | Reads | Writes |
|---|---|---|
| `make scrape` | `www.nawaloka.com`, 89 URLs | `knowledge/scraped/`, 82 documents |
| `make index` | that corpus | Qdrant, 834 chunks, and 89 harvested FAQ entries |
| `make seed` | `knowledge/data.sql` | `knowledge/hospital.db`, 5 tables, 64 rows |

Every decision, with its reason and the alternatives rejected, is in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). The same system is drawn seven
ways in [`docs/diagrams`](docs/diagrams).

## Results

| | |
|---|---|
| Routing accuracy | **29/29** |
| Retrieval hit rate | **21/22** in the top 5, mean reciprocal rank 0.93 |
| SQL execution accuracy | **17/17**, checked against the rows, not the route |
| FAQ fast path | 51 ms median, no model call |
| Corpus | 82 documents, 834 chunks, from 89 URLs |
| Database | 10 specialities, 11 doctors, 15 sessions, 17 lab tests, 11 packages |
| Tests | 122, with `ruff`, `ruff format` and `pyright` clean |

The three scores come from one `make evaluate` run.

## Prerequisites

| | Purpose | |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | Manages the Python version and the dependencies | Required |
| [Groq API key](https://console.groq.com/keys) | Free tier, no billing details | Required |
| `make` | Shortcut for every command. Linux and macOS ship it | Optional, see [Windows](#windows-without-make) |
| Python 3.12 | Pinned in `.python-version` | Fetched by uv |

### Installing uv

**Linux and macOS**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**macOS, with Homebrew**

```bash
brew install uv
```

**Windows, PowerShell**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

The installer does not change the shell that ran it. Open a new terminal, or on
Linux and macOS run `source $HOME/.local/bin/env`, then confirm:

```bash
uv --version
```

If that prints a version, everything below will work. If the command is not
found, the PATH has not been picked up yet.

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/udaraKavishka/Agentic-Healthcare-Assistant.git
cd Agentic-Healthcare-Assistant
```

### 2. Add your API key

```bash
cp .env.example .env  
```

Then paste your key into `GROQ_API_KEY`.

### 3. Install, then build the data

```bash
make install                # creates .venv, installs from the lockfile
make seed                   # data.sql -> knowledge/hospital.db
make index                  # committed corpus -> vector store
```

Nothing needs activating: every command runs through `uv run`, which uses
`.venv` itself. The first `make index` downloads about 130 MB of ONNX weights,
and later runs re-embed only the chunks whose text changed.

Only if you intend to re-crawl the hospital site, install the browser the
crawler drives. `uv sync` does not install it, and the corpus is committed, so
the assistant runs without this:

```bash
uv run playwright install chromium
```

### Windows, without make

`make` is the only part of this project that is not cross-platform. Every target
is one command, so nothing is lost by running them directly:

| Target | Direct command |
|---|---|
| `make install` | `uv sync` |
| `make seed` | `uv run python manage.py seed` |
| `make index` | `uv run python manage.py build-index` |
| `make scrape` | `uv run python manage.py scrape` |
| `make evaluate` | `uv run python manage.py evaluate` |
| `make run` | `uv run uvicorn assistant.api.app:app --reload --port 8000` |
| `make ui` | `uv run streamlit run app.py` |
| `make test` | `uv run pytest tests/ --tb=short` |
| `make lint` | `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright` |

Only `make dev` and `make tmux` have no Windows equivalent: one uses a bash
`trap`, the other needs tmux. Run the API and the UI in two terminals instead.

If you would rather have the targets, install `make` with whichever package
manager you already have:

```powershell
winget install ezwinports.make      # winget
choco install make                  # Chocolatey
scoop install main/make             # Scoop
```
## Run it

Two processes. Any one of these:

```bash
make dev                    # both, one terminal
make tmux                   # both, in a tmux session named `assistant`
make run                    # API only, on :8000
make ui                     # UI only, on :8501
```

Then open <http://localhost:8501>. The API serves `/docs` and `GET /health`.

Under tmux: `Ctrl-b d` detaches, `tmux attach -t assistant` returns, and
`tmux kill-session -t assistant` stops everything.

The vector store is embedded and single-process, so **stop the API before
`make index`**. The command says so if you forget.

## Evaluation

```bash
make evaluate               # routing, retrieval, SQL execution
```

Three scores, because they fail independently: routing can be right while
retrieval returns the wrong page, and both can be right while a query filters on
the wrong argument. Each golden set is weighted towards what breaks, including
prose columns that live in SQL, the `'Daily'` clinic, dual-source questions and
clinical refusals.

Retrieval runs entirely locally, so it needs the vector store built and the API
stopped. Routing and SQL execution call the model.

## Testing and quality gate

```bash
make check                  # ruff, ruff format, pyright, pytest
```

`requirements.txt` and `requirements-dev.txt` are exported from `uv.lock` by a
pre-commit hook, so they cannot drift from what is installed. Install the hooks
once with `uv run pre-commit install`.

## Refreshing the corpus

```bash
uv run playwright install chromium    # once per machine
make scrape                           # render the website into knowledge/scraped/
make index
```

`knowledge/scraped/` is committed, so a reviewer never has to re-crawl the
hospital's site. `make index` also rewrites `knowledge/faq.harvested.yml` from
the FAQ sections the site publishes, so the fast path refreshes with the site
rather than being hand-maintained.

The site is a client-side React application, so the crawler drives a headless
browser. It seeds from the sitemap but then follows links, because the sitemap
is stale: it advertises pages that no longer render and omits live ones.

## Project structure

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
docs/              architecture, diagrams
```

## Safety

The agent cannot write to the hospital database and cannot reach outside its
five tables. Four independent walls: the connection is opened read-only at the
driver, `PRAGMA query_only` is set behind it, any generated SQL is validated
against the parse tree with a table allowlist, and every query carries a row
limit and a deadline.

Clinical questions are a routing decision rather than a prompt instruction. They
short-circuit to a fixed referral before the answer model is called.


## Troubleshooting

**"The assistant is busy."** The free tier allows 30 requests and 8,000 tokens a
minute. The limiter waits for headroom and, past 20 seconds, says so rather than
hanging.

**"The vector store is already open."** The API is holding it. Stop the API,
then run `make index`.

## Author

**Udara Nalawansa**

[udaradev.me](https://udaradev.me) ·
[github.com/udaraKavishka](https://github.com/udaraKavishka) ·
[hello@udaradev.me](mailto:hello@udaradev.me)
