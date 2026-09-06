# Architecture and decisions

A hybrid agentic assistant for Nawaloka Hospitals. Each question goes to
whichever source holds the answer: scraped website content in a vector store,
hospital records in a relational database, or both.

---

## The system

| Component | Role | Built with |
|---|---|---|
| `assistant/api/` | `POST /chat` as server-sent events | FastAPI, uvicorn |
| `assistant/pipeline.py` | Sequences one turn | asyncio |
| `assistant/nodes/` | `faq`, `route`, `retrieve_sql`, `retrieve_vector`, `synthesize` | |
| `assistant/tools/` | Typed SQL queries and their schemas | |
| `assistant/database/` | Seeder, read-only connection, AST guard | SQLite, sqlglot |
| `assistant/knowledge_base/` | Chunking, embeddings, hybrid search, FAQ harvesting | Qdrant, fastembed |
| `assistant/llm/` | Groq client, rate-limit budget | Groq |
| `assistant/memory/` | Conversation turns, in their own writable database | SQLite |
| `assistant/scrape/` | robots, sitemap, headless crawl, PDF text | Playwright |
| `assistant/evaluate/` | Routing, retrieval and SQL scorers | |
| `web/` | Chat UI | Streamlit |
| `configs/prompts.yml` | Every word given to a model or shown to a patient | |

### One turn

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

### What the build produces

| Command | Reads | Writes |
|---|---|---|
| `make scrape` | `www.nawaloka.com`, 89 URLs | `knowledge/scraped/`, 82 documents |
| `make index` | that corpus | Qdrant, 834 chunks; 89 harvested FAQ entries |
| `make seed` | `knowledge/data.sql` | `knowledge/hospital.db`, 5 tables, 64 rows |

No model is called during the build.


## 1. API layer: FastAPI

The answer streams, so it needs an async framework with a streaming response
type. Pydantic is already a hard dependency, so FastAPI's validation and its
`/docs` page cost nothing extra.

## 2. Chat UI: Streamlit

Streamlit
calls the API server-side over `httpx`, so nothing depends on browser CORS and
there is no second build step.

## 3. Web scraping: headless Chromium

Every URL returns the same 863-byte shell with an empty `<div id="root">`, so a
static fetch shows nothing and Playwright renders each page. Four
details came from failures: navigate rather than use `page.request`, because the
host serves an incomplete certificate chain that only Chromium completes; wait
on rendered text, because React mounts a "Loading..." placeholder first; follow
links, because the sitemap advertises three dead pages and omits live ones; and
parse `robots.txt` with `protego`, because `urllib` matches first-wins and reads
the opening `Allow: /` as blanket permission.

Extraction takes `<main>` where present, `pypdf` recovers 12 governance PDFs,
and the crawl runs at one request per second.

**The doctor directory was found and left out.** The channeling
pages call an undocumented JSON backend at
`POST /nawaloka-care/care_backend/`, three endpoints deep:

| Endpoint | Payload | Returns |
|---|---|---|
| `get_echannelling_speciality_list` | none | 909 specialities and services, each with an `sp_id` |
| `get_doctor_list/` | `{"sp_id": 26, "date": "Any", "name": "*"}` | Every doctor in that speciality, 79 for `sp_id` 26 |
| `get_doctor_sessions` | `{"doc_id": "D0836"}` | Profile plus every session: day, time, room and fee |

Enumerating specialities and then doctors would yield the live directory with
real consultation fees and channeling times. It is not scraped, because the brief
puts doctor details and schedules in the structured data and states that the
prices and schedules in `data.sql` are hypothetical values generated for
evaluation. Indexing the live directory would put the vector store in direct
conflict with the database on exactly the questions routing sends to SQL, and the
`sql` route is supposed to win those.

## 4. Vector database: Qdrant, embedded

Qdrant fuses sparse and dense retrieval server-side in one Query API call, so
hybrid search costs one request rather than a hand-rolled BM25 index plus fusion
code.

**Rejected:** Chroma, weaker hybrid support; FAISS, a library rather than a
store; hosted stores, which put a network hop in front of an offline reviewer.

## 5. Relational database: SQLite, read-only

Five tables and 64 rows need no server, and SQLite ships with Python. More
importantly it can be opened where writing is impossible, at the driver with
`mode=ro` and at the engine with `PRAGMA query_only`, enforced by the database
rather than by our code.

**Rejected:** MySQL and Postgres, both correct for a real deployment and both
requiring a running server for 64 rows. Conversation memory lives in a separate
file, because the hospital database being unwritable is the point.

## 6. Querying it: typed tools, not text-to-SQL

The brief asks for a tool **or** text-to-SQL; this is the tool path. Four
functions wrap parameterised queries, every value arrives as a bound parameter,
so this path never builds SQL from text.

```
find_doctors(specialty, name, max_fee)    get_schedule(doctor_name, day)
find_lab_tests(query)                     find_health_packages(query)
```

Three schema traps live in the templates rather than in a prompt, because a
prompt the model forgets produces a wrong answer with no error: a clinic stored
as `day_of_week = 'Daily'` rather than seven weekday rows; prose columns that are
searched word by word and ranked by how many matched; and specialities matched by
stem, because the column says `Cardiology` and the patient says cardiologist.

**Generated SQL is not built, but its safety is**, in `guard.py` with 14 tests:

| Wall | Mechanism | Stops |
|---|---|---|
| 0 | No SQL generated; bound parameters | Injection, on the path in use |
| 1 | `sqlglot` allowlist over the whole parse tree | `WITH d AS (DELETE ... RETURNING *) SELECT * FROM d` |
| 2 | `LIMIT` injected or clamped by AST rewrite | A join emptying the database into a prompt |
| 3 | `mode=ro` plus `PRAGMA query_only` | Any write, even past walls 1 and 2 |
| 4 | Progress-handler deadline | A runaway query |


## 7. Seeding and indexing

`data.sql` is MySQL and `INT PRIMARY KEY AUTO_INCREMENT` parses nowhere else, so
two regular expressions shim the dialect at load time and the provided file stays
untouched. `make seed` drops and recreates, so it is idempotent.

Indexing walks the corpus once and feeds both the vector store and the harvested
FAQ. It is incremental: each point id is a `uuid5` over the model name, URL and
contextualised text, so unchanged chunks are never re-embedded and a model switch
invalidates everything at once.

## 8. The agentic pipeline

A deterministic pipeline with exactly one LLM decision, not an agent loop. With
two kinds of tool there is one interesting decision, and every extra step
multiplies error.
Tool execution is code rather than a model choice, which removes hallucinated
tool names and makes the route auditable.

**Rejected:** ReAct, unbounded turns at roughly five times the tokens;
plan-then-execute, nothing to plan across two tools; a multi-agent supervisor.

## 9. Routing between vector, SQL, and both

One call to the small model returns the route label, the question rewritten to
stand alone, and a reason.

| Route | Goes to | For |
|---|---|---|
| `sql` | Hospital database | Fees, schedules, prices, package contents, who practises what |
| `vector` | Website corpus | Services, centres, facilities, rooms, policies |
| `both` | Both, concurrently | Questions spanning the two |
| `faq` | Fixed answer | Greetings, questions about the assistant |
| `refuse` | Fixed referral | Symptoms, diagnosis, medication |

The label is returned rather than inferred from which tools were called, so it is
one decision and checkable against a golden set. Routing policy lives in the tool
descriptions, because that is what the model reads when choosing.

**The trap this avoids:** two SQL columns hold prose, so "which package includes
a Pap smear?" reads unstructured and a surface-texture router sends it to the
vector store, where the answer does not exist. Route by where the truth lives.

**Measured: 34 of 34**, as a confusion matrix, because failures are directional.

## 10. Model selection

| Job | Model |
|---|---|
| Route, rewrite, pick tool arguments | `gpt-oss-20b` |
| Write the patient-facing answer | `gpt-oss-120b` |

Classification work goes to the cheap model and the patient-facing answer to the
larger one. Rate limits are per model, so the split also widens the usable quota.

## 11. Rate limiting and graceful degradation

A rolling-window bucket over both requests and tokens, reserved before the call
rather than discovered after it, which turns a burst into a short wait instead of
a wall of errors. The ceiling is per caller: 20 seconds for a patient, 90 for a
batch eval.

Every dead end names what it cannot do, then offers what it can, and the plumbing
goes to the log. "The rate limit needs 31 seconds of headroom" describes a
billing tier and is useless to a patient. Waits and faults are worded apart,
because calling a bug "load" would make the interface disagree with the logs.

## 12. Safety and scope

Refusal is a route rather than a prompt instruction, because a system-prompt rule
leaks under multi-turn pressure. Clinical questions short-circuit to a reviewed
string without reaching the answer model, and over-refusal is measured with
in-scope near misses in the golden set.

Abstention is explicit, because vector search never says "nothing matched", it
returns its nearest *k*. Citations come from the passages actually retrieved,
after `gpt-oss` was found inventing marker numbers like `【9】` against a
five-passage context.

---

# Bonus criteria

## 13. FAQ handling: speed and accuracy

A local similarity gate runs before any model call, embedding the message with
the same ONNX model used for retrieval and answering method on a hit.
Greetings and questions about the assistant carry no hospital fact to retrieve,
so routing them costs two model calls for a reply that never varies.

Hand-written FAQs go stale, so `make index` harvests every published FAQ section
from the corpus into 89 more entries, each carrying its source URL and cited like
a retrieved answer. The gate holds only facts about the assistant and contact
details; anything about a doctor or a price stays in SQL.

## 14. Improved retrieval quality

Five strategies.

| Strategy | Against |
|---|---|
| Dense plus BM25, fused server-side by RRF | Dense-only misses exact tokens: a consultant's name, `LAB-DENGUE` |
| Cross-encoder rerank, 20 candidates to 5 | The bi-encoder cannot read query and passage together |
| Contextual chunk prefixes | "Book an appointment" is context-free without its page and heading |
| ONNX throughout, `MiniLM-L-6` reranker | 2.5 GB of Torch to reorder five passages|
| Page diversity, at most two chunks per page| One article filling the whole prompt |

**Measured: 22 of 22 in the top five, MRR 0.94**, up from 21 of 22 at 0.93.

## 15. Agentic memory across multi-turn conversations

A persistent verbatim window in its own SQLite file, keyed by a conversation id
the browser sends with every turn, plus the follow-up rewrite folded into the
routing call.

Verbatim rather than summarised, because pronoun resolution depends on exact
wording: a summary compressing "Dr Prakash Priyadarshan, Consultant Cardiologist"
into "a cardiologist" discards what "what does he charge?" needs. The rewrite
happens inside the routing call because "and his fee?" is not merely
unretrievable, it is unroutable, and a separate call would double requests per
turn.

**Measured: 5 of 5 follow-ups resolve**, including one adversarial case where a
change of subject must *not* be rewritten into the previous topic. Five more
tests cover the store itself: persistence across processes, ordering,
conversation isolation, and the window bound.

**Rejected:** mem0, Zep and Letta, which solve cross-session personalisation for
identified users. This assistant serves anonymous visitors, so there is no
identity to attach memory to.

---

## Results

| | |
|---|---|
| Routing | 34 of 34, including 5 multi-turn |
| Retrieval | 22 of 22 in the top five, MRR 0.94 |
| SQL execution | 17 of 17, checked against the rows |
| FAQ fast path | 55 ms median, no model call |

One `make evaluate` run produces all three. They fail independently: routing can
be right while retrieval returns the wrong page, and both can be right while a
query filters on the wrong argument.

## Deliverables, and what was added for evaluation

| Artefact | Why | Evidences |
|---|---|---|
| `evals/questions.yml`, 34 cases | Routing is graded, so it is measured. 5 are multi-turn. | Routing accuracy |
| `evals/retrieval.yml`, 22 cases | Routing says the question arrived; it says nothing about what came back. | Agent performance |
| `evals/sql.yml`, 17 cases | A query can route correctly and still filter wrongly. It found three real bugs. | Agent performance |
| 129 tests across ten areas | Weighted towards quiet failures: the SQL guard alone has 14. | Code quality |
| Two GitHub Actions workflows | pre-commit and the suite, on push, pull request, or by hand. | Code quality |
| pre-commit with a requirements export | `requirements.txt` comes from `uv.lock`, so it cannot drift. | Deliverable |
| `docs/DIAGRAMS.md`, `docs/diagrams/` | Seven views of the system. | Architectural decisions |
| `Makefile` | One command surface, so a reviewer never assembles a command. | Deliverable |
| The committed corpus | 82 documents, so nobody re-crawls a hospital's site. | Deliverable |
