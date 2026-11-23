# whowhen-rag

**Find the "who" and "when" in a search query, and only pay for the extra LLM call when there is one.**

`whowhen-rag` turns questions like *"what did Priya change in the pricing docs last week?"* into metadata filters for your RAG system:

```python
f = detector.detect("what did Priya change in the pricing docs last week?")
f.conditions     # [Condition('modified_on', '>=', '2026-11-09'),
                 #  Condition('modified_on', '<', '2026-11-16'),
                 #  Condition('last_editor', '=', 'priya@example.com')]
f.cleaned_query  # 'pricing docs'  (use this for the semantic search)
f.to_sql()       # ('"modified_on" >= %s AND "modified_on" < %s AND "last_editor" = %s', [...])

f = detector.detect("latest deployment runbook")
f.conditions     # []          (no period, so nothing is excluded)
f.recency        # 'newest'    (a hint: show the most recent material first)
```

It works with any vector store or database, any LLM, and any column names.

## Why it is cheap

Most questions sent to a knowledge base have no time or author condition at all. Framework tools for this (LangChain's `SelfQueryRetriever`, LlamaIndex auto-retrieval) make an **extra LLM call on every query** to find out. `whowhen-rag` puts two cheap gates in front of that extra call:

```
query
  │
  ├─ 1. Regex gate ......... free.  "last week", "written by", "latest" ... ─────────┐
  │      miss                                                                         │ hit
  ├─ 2. Jev ................ one call, two multiple-choice answers, no text            │
  │                          generation: needs a filter? newest/oldest? ──────────────┤ yes
  │      no: return "no filter" (plus the recency hint), no extraction call           │
  │                                                                                   ▼
  └─ 3. Your LLM ........... extracts dates and names. Only for likely filters.
                             On a regex hit, Jev's recency question runs alongside it.
```

- **Gate 1** catches the common wording for free.
- **Gate 2** ([Jev](https://pypi.org/project/typesafe-sdk/)) catches unusual wording ("anything Priya put together on onboarding?"), and answers whether the query wants the newest or oldest material. It gives probabilities, not text, so it cannot pull out dates or names, which is why step 3 exists.
- **Step 3** runs only when a gate says yes, so plain questions ("how does caching work?") never cost an extraction call.

"No LLM call" here always means no *filter-extraction* call by `whowhen-rag`. Your RAG pipeline still calls its own LLM to answer the question, as it would anyway; `whowhen-rag` only decides whether an extra call to find filters is needed.

Every result carries a `trace` (which gate fired, whether Jev and the LLM ran, Jev's confidences and both latencies), so you can measure the savings on your own traffic.

### Measured

**The benchmark.** 119 hand-written questions, each labelled in advance with the exact answer: which date range, which person, whether it asks for the newest or oldest material, or nothing at all. Today is fixed at 2026-11-18 so the expected dates never go stale. Every question goes through the real pipeline (regex, Jev, the LLM) exactly as in your application, with Claude Haiku 5.5 as the LLM. The script is [`benchmarks/run.py`](https://github.com/rahulbansalc6414/whowhen-rag/blob/main/benchmarks/run.py) and the questions are in [`benchmarks/cases.py`](https://github.com/rahulbansalc6414/whowhen-rag/blob/main/benchmarks/cases.py).

| The 119 questions | Count |
|---|---|
| Need a filter or recency hint ("what did Priya change last week?", "latest runbook") | 81 |
| Plain, need nothing ("how does caching work?", "who owns the retention policy?") | 37 |
| Either answer acceptable | 1 |

**Did we catch all of them?**

| Step | Result |
|---|---|
| Questions that need a filter, sent on to the LLM | **81 of 81**: the regex caught 72, Jev caught the other 9 (confidence 0.68 to 1.00). None was missed. |
| Plain questions stopped before the LLM (no extraction call) | **30 of 37**. The other 7 (five "who wrote / owns / updated X?" caught by the regex, two let through by Jev) came back from the LLM as "no filter", so the user saw no difference. |
| Questions asking for the newest or oldest material, found by Jev | **16 of 16** |
| Dates and people extracted correctly by the LLM | **85 of 89** calls |
| **Fully right end to end** (filters and recency hint) | **113 of 119 (95%)** |

The 6 that are not fully right: two questions with a period but no year ("design docs updated since December", "meeting notes from Q3") came back with no filter, so the user gets an ordinary search; two picked the created date where the label said updated, or the reverse, which is arguable either way; and two ("any new incident reports today?", "anything new ... since Monday") got the right date filter plus a "newest" hint the label did not ask for.

**Speed and cost.** A query takes about 0.9 s (median): Jev about 0.3 s, the LLM about 0.95 s, run in parallel on a regex hit. An extraction call costs about **0.013 cents** with Haiku 5.5 (about 13 cents per 1,000 calls). Jev calls are billed separately by TypeSafe.

**Haiku 4.5 on the same benchmark:** 114 of 119, at about 8 times the cost per extraction and about 25% slower. The two models miss different questions: on the three periods without a year, Haiku 4.5 got two right and put "since September" in the wrong year; Haiku 5.5 got one right and left the filter out on the other two. Details and the full history of every run are in [`benchmarks/RESULTS.md`](https://github.com/rahulbansalc6414/whowhen-rag/blob/main/benchmarks/RESULTS.md).

These are small, hand-written sets. Measure on your own queries before relying on the numbers.

## Install

```bash
pip install whowhen-rag
```

## Quick start

```python
from whowhen_rag import Detector, Field

detector = Detector(
    fields=[
        Field("created_on",  role="created_at"),
        Field("modified_on", role="updated_at"),
        Field("owner_email", role="created_by", resolve=lookup_email),  # name -> your stored value
    ],
    llm=my_llm,  # any function: prompt string in, answer string out
)

f = detector.detect("pages Priya wrote this month about onboarding")
if f:                                    # same as f.needs_filter
    where, params = f.to_sql()
    search_text = f.cleaned_query        # "onboarding"
```

Set `TYPESAFE_API_KEY` for the Jev classifier. A runnable example with sqlite is in [`examples/quickstart.py`](https://github.com/rahulbansalc6414/whowhen-rag/blob/main/examples/quickstart.py).

## Your columns, your names

You declare your columns once. The LLM never sees them: it answers in terms of four **roles**, and `whowhen-rag` maps each role to your column.

| Role | Meaning |
|---|---|
| `created_at` | when the document was created |
| `updated_at` | when the document was last edited |
| `created_by` | who created or wrote it |
| `updated_by` | who last edited it |

Declare only the roles you have. If you have one date column, "changed last week" and "created last week" both use it.

```python
Field(
    "author_id",                               # your column or metadata key
    role="created_by",
    resolve=lambda name: users.find_id(name),  # str, int, list of IDs, or None if unknown
)
Field(
    "updated_ts",
    role="updated_at",
    value_format="epoch",                      # "date" (default), "datetime", "epoch", "epoch_ms"
    description="when the ticket was last touched",  # optional wording for the LLM
)
```

- **`resolve`** turns a name from the query into what your column stores. Without it, the name is used as written. If it returns `None`, that condition is dropped and the name is listed in `f.trace.unresolved_people`.
- **`value_format`** matches how your dates are stored. Dates are midnight UTC.

### Time zones

"Today", "yesterday" and "this week" are worked out from today's date, which is UTC by default. If your users are far from UTC, pass their date, or "yesterday" will be off by a day around midnight:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

Detector(fields, llm, today=lambda: datetime.now(ZoneInfo("Asia/Singapore")).date())
```

The date is read on every query, so nothing needs updating as the years pass.

## Bring your own LLM

`llm` is any function that takes the prompt and returns the model's text. `whowhen-rag` writes the prompt and validates the answer. Benchmarked with Claude Haiku 5.5 (thinking off) and Haiku 4.5; any model that follows JSON instructions should work.

**Anthropic** (Claude Haiku 5.5, thinking off: faster and cheaper, and it scored the same with thinking on in our tests)

```python
import anthropic

client = anthropic.Anthropic()

def llm(prompt: str) -> str:
    msg = client.messages.create(model="claude-haiku-5-5", max_tokens=1024,
                                 thinking={"type": "disabled"},
                                 messages=[{"role": "user", "content": prompt}])
    return next(b.text for b in msg.content if b.type == "text")
```

**OpenAI or OpenRouter**

```python
from openai import OpenAI

client = OpenAI()  # OpenRouter: OpenAI(base_url="https://openrouter.ai/api/v1", api_key=...)

def llm(prompt: str) -> str:
    r = client.chat.completions.create(model="gpt-4o-mini", temperature=0,
                                       messages=[{"role": "user", "content": prompt}])
    return r.choices[0].message.content or ""
```

## Prompts

The extraction prompt is a plain text file, versioned and measured. `v4` is the default; `v1` and `v2` are kept so you can see what changed and why.

```python
Detector(fields, llm, prompt="v2")             # an older built-in version
Detector(fields, llm, prompt="my_prompt.txt")  # your own template
```

v2 fixed five failure patterns found by the benchmark ("in October" read as last year, a year in a topic name read as a filter, and others). v3 tried two more rules and did worse, so it was not shipped. v4 is v2 without any sorting rules: recency moved to Jev, and the LLM is told never to turn "latest" or "recent" into a date range. See [`docs/prompts.md`](https://github.com/rahulbansalc6414/whowhen-rag/blob/main/docs/prompts.md) for the before and after, the template placeholders, and how to score your own prompt.

## The classifier (Jev)

On by default. It reads `TYPESAFE_API_KEY`, or you pass the key. It answers two questions:

| Question | When it is asked | Setting |
|---|---|---|
| Does the query need a filter? | only when the regex missed | `threshold=0.6`: yes when P(filter) >= 0.6 |
| Newest, oldest or neither? | every query: together with the first question in one call, or alongside your LLM on a regex hit | `recency_threshold=0.95`: the hint is given only when Jev is at least this sure |

```python
from whowhen_rag import Detector, JevClassifier

Detector(fields, llm, classifier=JevClassifier(api_key="...", threshold=0.6, recency_threshold=0.95))
Detector(fields, llm, use_classifier=False)      # regex gate only, no recency hint
Detector(fields, llm, classifier=my_classifier)  # any function query -> bool: filter gate only, no recency hint
```

Without a key, `whowhen-rag` logs one warning and carries on with the regex gate only: queries the regex misses get no filter, and there is no recency hint.

## What "recent" means

"Latest deployment runbook" and "deployment runbook changes last week" are different requests:

| Query | `f.conditions` | `f.recency` |
|---|---|---|
| "latest deployment runbook" | none | `"newest"` |
| "deployment runbook changes last week" | `modified_on >= 2026-11-09`, `< 2026-11-16` | `None` |
| "latest runbook changes this month" | `modified_on >= 2026-11-01` | `"newest"` |
| "oldest page about the billing service" | none | `"oldest"` |

A period ("last week", "this month", "yesterday") becomes a condition and excludes everything outside it. A recency word with no period ("latest", "newest", "these days", "what's new") never excludes anything: it becomes the `recency` hint, and you decide what to do with it.

`whowhen-rag` deliberately does not pick a date column for the hint or sort for you. Two suggestions:

- **Use your "last updated" date.** A document created long ago and edited yesterday is the "latest" one to most users, and a brand-new document's update date is its creation date, so updated dates catch both.
- **Rerank, don't sort everything.** Ordering a whole search by date buries relevance: "latest runbook" would return the newest documents on any topic. Take your top matches by relevance (say 20), then order those by date, or blend the two scores.

## Using the result

| | |
|---|---|
| `f.needs_filter`, `bool(f)` | any condition, recency hint or list request found |
| `f.conditions` | `Condition(column, op, value)`; op is `>=`, `<`, `=` or `in`; combine with AND |
| `f.recency` | `"newest"`, `"oldest"` or `None`: a hint, see [What "recent" means](#what-recent-means) |
| `f.cleaned_query` | the query without its time, person and recency words, for semantic search |
| `f.list_only` | the query only asks to list documents ("pages Priya created this week"); you can skip semantic search |
| `f.to_sql(placeholder="%s")` | `(where_clause, params)`: columns quoted, values parameterised; `"?"` for sqlite |
| `f.to_chroma()` | a Chroma `where` dict (Chroma ranges need numbers: use `value_format="epoch"`) |
| `f.to_qdrant()` | a Qdrant filter dict: `models.Filter(**f.to_qdrant())` |
| `f.to_dict()` | plain dict, JSON-serialisable |
| `f.trace` | which gate fired, whether Jev and the LLM ran, Jev's confidences, latencies, errors |

Only need the yes or no? `detector.has_signal(query)` runs the cheap gates and never calls the LLM.

`has_signal` is the gates' guess *before* extraction; `needs_filter` is the answer *after* it. They can differ one way: "who wrote the incident playbook?" passes the regex (`has_signal` is True), but asks *who* rather than limiting documents, so extraction finds no filter (`needs_filter` is False). If `has_signal` is False, `needs_filter` is always False.

## Failure behaviour

Search should never break because of filtering. If Jev or the LLM fails, times out or returns something unusable, `detect()` returns "no filter" with the original query and logs a warning (logger `whowhen_rag`). If only the LLM fails, the recency hint from Jev is still returned. The LLM's answer is validated: unknown roles, invalid dates and empty ranges are dropped, never guessed.

## Limitations

- English queries only (the regex gate and the prompt are English).
- Synchronous. Use `asyncio.to_thread` from async code. (On a regex hit, `detect()` runs Jev and your LLM on two threads internally.)
- Months named without a year ("since September") are occasionally put in last year by the LLM. An experimental correction is available with `Detector(..., fix_years=True)`; it is off by default.
- Four roles (created and updated, time and person). "My documents" needs the current user, which `whowhen-rag` does not know.

## Development

```bash
uv sync
uv run pytest                      # no network or API keys needed
uv run python benchmarks/run.py    # the benchmark: needs TYPESAFE_API_KEY and OPENROUTER_API_KEY
```

## License

MIT
