# whowhen

**Find the "who" and "when" in a search query, and only pay for an LLM when there is one.**

`whowhen` turns questions like *"what did Priya change in the pricing docs last week?"* into metadata filters for your RAG system:

```python
f = detector.detect("what did Priya change in the pricing docs last week?")
f.conditions     # [Condition('modified_on', '>=', '2026-11-09'),
                 #  Condition('modified_on', '<', '2026-11-16'),
                 #  Condition('last_editor', '=', 'priya@example.com')]
f.cleaned_query  # 'pricing docs'  (use this for the semantic search)
f.to_sql()       # ('"modified_on" >= %s AND "modified_on" < %s AND "last_editor" = %s', [...])
```

It works with any vector store or database, any LLM, and any column names.

## Why it is cheap

Most questions sent to a knowledge base have no time or author condition at all. Framework tools for this (LangChain's `SelfQueryRetriever`, LlamaIndex auto-retrieval) send **every** query to an LLM to find out. `whowhen` puts two cheap gates in front of the LLM:

```
query
  │
  ├─ 1. Regex gate ......... free.  "last week", "written by", "latest" ... ───────┐
  │      miss                                                                       │ hit
  ├─ 2. Jev classifier ..... a yes/no answer, no text generation. ─────────────────┤ yes
  │      no: return "no filter", no LLM call                                        │
  │                                                                                 ▼
  └─ 3. Your LLM ........... extracts dates, names, sort order. Only for likely filters.
```

- **Gate 1** catches the common wording for free.
- **Gate 2** ([Jev](https://pypi.org/project/typesafe-sdk/)) catches unusual wording ("anything Priya put together on onboarding?"). It answers yes or no with a probability. It cannot pull out the dates or names, which is why step 3 exists.
- **Step 3** runs only when a gate says yes, so plain questions ("how does caching work?") never reach a paid model.

Every result carries a `trace` (`gate`, `classifier_called`, `llm_called`), so you can measure the savings on your own traffic.

### Measured

On the synthetic benchmark sets (details and history in [`benchmarks/RESULTS.md`](https://github.com/rahulbansalc6414/whowhen/blob/main/benchmarks/RESULTS.md)):

- **Plain questions:** 20 of 20 stopped by the gates. No LLM call.
- **Unusual wording the regex misses:** 8 of 8 caught by the Jev classifier.
- **Extraction** (Claude Haiku 4.5, prompt v2): **13 of 15** exactly right (dates, people, sort) on a fresh set written after the prompt was final, and 45 of 45 on the sets used while writing it. Misses on the fresh set: "since September" read as last year, and one arguable person filter.
- **Cost of an extraction:** about 750 input and 75 output tokens, about **$0.0011** at Haiku 4.5 list price (about $1.10 per 1,000 queries that reach the LLM), median 1.6 s.

These are small, hand-written sets. Measure on your own queries before relying on the numbers.

## Install

```bash
pip install whowhen
```

## Quick start

```python
from whowhen import Detector, Field

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

Set `TYPESAFE_API_KEY` for the Jev classifier. A runnable example with sqlite is in [`examples/quickstart.py`](https://github.com/rahulbansalc6414/whowhen/blob/main/examples/quickstart.py).

## Your columns, your names

You declare your columns once. The LLM never sees them: it answers in terms of four **roles**, and `whowhen` maps each role to your column.

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

## Bring your own LLM

`llm` is any function that takes the prompt and returns the model's text. `whowhen` writes the prompt and validates the answer. Tested with Claude Haiku 4.5; any model that follows JSON instructions should work.

**Anthropic**

```python
import anthropic

client = anthropic.Anthropic()

def llm(prompt: str) -> str:
    msg = client.messages.create(model="claude-haiku-4-5", max_tokens=512,
                                 messages=[{"role": "user", "content": prompt}])
    return msg.content[0].text
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

The extraction prompt is a plain text file, versioned and measured. `v2` is the default; `v1` is kept so you can see what changed and why.

```python
Detector(fields, llm, prompt="v1")             # an older built-in version
Detector(fields, llm, prompt="my_prompt.txt")  # your own template
```

v2 fixed five failure patterns found by the benchmark ("in October" read as last year, a year in a topic name read as a filter, and others), going from 37 to 45 of 45 correct on the sets used while writing it, and 13 of 15 on a fresh set. See [`docs/prompts.md`](https://github.com/rahulbansalc6414/whowhen/blob/main/docs/prompts.md) for the before and after, the template placeholders, and how to score your own prompt.

## The classifier (Jev)

On by default. It reads `TYPESAFE_API_KEY`, or you pass the key:

```python
from whowhen import Detector, JevClassifier

Detector(fields, llm, classifier=JevClassifier(api_key="...", threshold=0.5))
Detector(fields, llm, use_classifier=False)      # regex gate only
Detector(fields, llm, classifier=my_classifier)  # any function: query -> bool
```

Without a key, `whowhen` logs one warning and carries on with the regex gate only; queries the regex misses then get no filter.

## Using the result

| | |
|---|---|
| `f.needs_filter`, `bool(f)` | any condition, sort or list request found |
| `f.conditions` | `Condition(column, op, value)`; op is `>=`, `<`, `=` or `in`; combine with AND |
| `f.sort` | `Sort(column, descending)` for "latest" or "oldest", else `None` |
| `f.cleaned_query` | the query without its time and person words, for semantic search |
| `f.list_only` | the query only asks to list documents ("pages Priya created this week"); you can skip semantic search |
| `f.to_sql(placeholder="%s")` | `(where_clause, params)`: columns quoted, values parameterised; `"?"` for sqlite |
| `f.order_by_sql()` | `ORDER BY "col" DESC`, or `""` |
| `f.to_chroma()` | a Chroma `where` dict (Chroma ranges need numbers: use `value_format="epoch"`) |
| `f.to_qdrant()` | a Qdrant filter dict: `models.Filter(**f.to_qdrant())` |
| `f.to_dict()` | plain dict, JSON-serialisable |
| `f.trace` | which gate fired, whether the classifier and LLM ran, errors |

Only need the yes or no? `detector.has_signal(query)` runs the cheap gates and never calls the LLM.

## Failure behaviour

Search should never break because of filtering. If the classifier or LLM fails, times out or returns something unusable, `detect()` returns "no filter" with the original query and logs a warning (logger `whowhen`). The LLM's answer is validated: unknown roles, invalid dates and empty ranges are dropped, never guessed.

## Limitations

- English queries only (the regex gate and the prompt are English).
- Synchronous. Use `asyncio.to_thread` from async code.
- Four roles (created and updated, time and person). "My documents" needs the current user, which `whowhen` does not know.

## Development

```bash
uv sync
uv run pytest                        # no network or API keys needed
uv run python benchmarks/gates.py    # set TYPESAFE_API_KEY to include the classifier
```

## License

MIT
