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
| Routing accuracy | **29/29** on the golden set |
| Retrieval hit rate | **21/22** in the top 5, mean reciprocal rank 0.93 |
| SQL execution accuracy | **15/16**, checked against the rows, not the route |
| Corpus | 82 documents, 834 chunks, from 89 URLs crawled |
| FAQ fast path | 8 curated answers, 89 harvested from the site's own FAQs, 51 ms median |
| Database | 10 specialities, 11 doctors, 15 sessions, 17 lab tests, 11 packages |
| Tests | 107, with `ruff`, `ruff format` and `pyright` clean |

All three scores come from `make evaluate`.

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

## Getting started

### What you need

- **Python 3.12** — pinned in `.python-version`. You do not have to install it
  yourself; `uv` fetches it.
- **[uv](https://docs.astral.sh/uv/)** — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **A Groq API key** — free, no billing: <https://console.groq.com/keys>

### Setup

```bash
git clone https://github.com/udaraKavishka/Agentic-Healthcare-Assistant.git
cd Agentic-Healthcare-Assistant

make install                # creates .venv and installs everything
cp .env.example .env        # then paste your key into GROQ_API_KEY
```

`make install` runs `uv sync`, which creates `.venv/` for you and installs from
the lockfile. There is no separate `python -m venv` step, and you never need to
activate the environment: every command below goes through `uv run`, which uses
`.venv` automatically.

If you prefer an activated shell, `source .venv/bin/activate` works and the
commands then run without the `uv run` prefix.

### Build the data

```bash
make seed                   # data.sql -> knowledge/hospital.db
make index                  # committed corpus -> vector store
```

The first `make index` downloads about 130 MB of ONNX model weights. Later runs re-embed only chunks whose text changed.

## Running it

The assistant is two processes: the API and the chat UI.

**In one terminal:**

```bash
make dev                    # API on :8000, UI on :8501
```

**In tmux**, if you would rather watch the two logs side by side:

```bash
make tmux                   # loads assistant_tmux.yaml
```

That opens a session named `assistant` with an `api` window, a `web` window and
a spare shell.

```bash
Ctrl-b d                            # detach, leaving both processes running
tmux attach -t assistant            # come back to them
tmux kill-session -t assistant      # stop the session and everything in it
```

Killing the session is what frees port 8000 and releases the vector store, so
run it before `make index`. If you have forgotten the name, `tmux ls` lists the
sessions and `tmux kill-server` stops all of them.

**Separately**, two terminals, which is the clearest way to read errors:

```bash
make run                    # terminal one: API on :8000
make ui                     # terminal two: UI on :8501
```

Then open <http://localhost:8501>. The API also serves `/docs` for the OpenAPI
schema and `GET /health` as a liveness check.

One thing to know: the vector store is embedded and single-process, so `make
index` cannot run while the API holds it. Stop the API first — the command
tells you if you forget.

## Refreshing the corpus

```bash
make scrape                 # render the website into knowledge/scraped/
make index
```

`knowledge/scraped/` is committed, so a reviewer never has to re-crawl the
hospital's site. Run `make scrape` only to refresh it.

`make index` also rewrites `knowledge/faq.harvested.yml`, the FAQ sections the
hospital publishes on its own pages, read straight out of the corpus. Those
answers are matched before any model runs, so the fast path refreshes with the
site instead of being hand-maintained.

The site is a client-side React application, so the crawler drives a headless
browser rather than fetching HTML. It seeds from the sitemap but follows links,
because the sitemap is stale: it advertises pages that no longer render and
omits live ones, including the health checkup packages.

## Evaluating

```bash
make evaluate               # routing, retrieval and SQL execution
```

Three scores, because they can be wrong independently of each other. Routing can
be right while retrieval returns the wrong page, and both can be right while a
query filters on the wrong argument.

**Routing**, from `evals/questions.yml`, reported as a confusion matrix. The set
is weighted towards what breaks: prose columns that live in SQL, the `'Daily'`
clinic, questions needing both sources, and clinical refusals. The matrix
matters more than the score, because *which way* routing fails decides whether a
patient gets a wrong answer or none.

**Retrieval**, from `evals/retrieval.yml`, where each question names the pages
that would let it be answered honestly. Reported as hit rate in the final top 5
and as mean reciprocal rank, so a page that only just made the prompt is not
scored like one that led it.

**SQL execution**, from `evals/sql.yml`, where each question names the template
the model should call and the facts that have to survive into the rows. This is
the only score that looks at the answer rather than the decision, and it is the
one that found "a health package for women over 40" missing the package whose
audience reads `Females 40 years and above` — right route, right tool, wrong
rows.

Only routing and SQL execution call the API. Retrieval runs entirely locally, so
it needs the vector store built and the API stopped.

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
  nodes/        faq, route, retrieve_sql, retrieve_vector, synthesize
  scrape/       robots, sitemap, headless crawl, PDF text
  tools/        typed SQL queries and their tool schemas
  evaluate/     routing, retrieval and SQL execution scores
  pipeline.py   one turn, top to bottom
web/            Streamlit chat UI
configs/        prompts.yml, every word the models are given
evals/          the three golden sets
knowledge/      data.sql, the committed corpus, the FAQ files
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
