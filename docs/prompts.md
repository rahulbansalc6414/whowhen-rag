# Prompts

The extraction prompt is a plain text template in [`src/whowhen/prompts/`](../src/whowhen/prompts/). It is the only part of `whowhen` that talks to your LLM, so it is the part most worth tuning.

| Version | File | Status |
|---|---|---|
| v1 | [`v1.txt`](../src/whowhen/prompts/v1.txt) | first version, kept for comparison |
| v2 | [`v2.txt`](../src/whowhen/prompts/v2.txt) | **default** |

```python
Detector(fields, llm)                         # v2
Detector(fields, llm, prompt="v1")            # an older built-in version
Detector(fields, llm, prompt="my_prompt.txt") # your own file
Detector(fields, llm, prompt=template_text)   # your own text
```

## How a template works

Four placeholders are filled in at query time. Every other brace is literal, so JSON examples need no escaping.

| Placeholder | Filled with | Required |
|---|---|---|
| `{query}` | the user's query (inserted last, so braces inside it are never read as placeholders) | yes |
| `{filters}` | one line per role you declared, e.g. `- updated_at: when the document was last edited` | yes |
| `{today}` | today's date, `2026-11-18` | yes |
| `{weekday}` | today's weekday, `Wednesday` | no |

A template missing a required placeholder is rejected when the `Detector` is created, not at query time.

Whatever the template says, the answer must be the JSON object v2 describes (`time_ranges`, `people`, `sort`, `list_only`, `cleaned_query`): that is what `whowhen` parses and validates.

## v1 to v2: what failed and what fixed it

v1 was measured on 45 synthetic queries (30 main, 15 held out) with Claude Haiku 4.5. It got 37 exactly right. Every failure fell into one of five patterns, and v2 adds one rule for each:

| v1 failure | Example | Rule added in v2 |
|---|---|---|
| A month without a year read as last year | "docs modified in October" (asked in November 2026) gave October 2025 | A month or quarter without a year means the most recent one that has started. Never a future period. |
| "last month" read as the last 30 days | "list documents created last month" gave Oct 18 to Nov 18 | "last month" = the previous calendar month, 1st to 1st. |
| A year in a topic name read as a filter | "how does the 2025 pricing model work" gave all of 2025 | A year, quarter or date that is part of a document's name or topic is not a filter. |
| A sort added when none was asked | "what changed ... last week?" gained sort by newest | Sort only when the query asks for an order (recent, latest, oldest...). |
| A period up to now ending at today | "past two weeks" ended at today, which drops today's documents | A period that runs up to now has end null. |

v2 also states `list_only` more precisely: it is true when only generic document words remain after removing the conditions ("docs modified in October").

| Prompt | Main (30) | Held out (15) | Tokens per call (in / out) |
|---|---|---|---|
| v1 | 26 | 11 | 545 / 78 |
| v2 | **30** | **15** | 750 / 75 |

On a **fresh** set of 15 queries written after v2 was final, v2 scored **13/15**: "since September" was still read as last year, and "what is Marco's opinion on the caching proposal" got a person filter (arguable). That is the honest number for v2, and the starting point for a v3.

The extra rules cost about 200 input tokens per call: about $0.0002 more per extraction with Haiku 4.5. The held-out queries were written before v2, but their v1 failures were seen while writing v2, so the v2 held-out score is not a clean held-out measurement. Full history: [`benchmarks/RESULTS.md`](../benchmarks/RESULTS.md).

## Writing your own

1. Copy `src/whowhen/prompts/v2.txt` and edit it: your domain's wording, another language, extra examples.
2. Score it on the benchmark sets (needs an OpenRouter key; 30 or 15 LLM calls):

   ```bash
   uv run python benchmarks/extraction.py --prompt my_prompt.txt
   uv run python benchmarks/extraction.py --prompt my_prompt.txt --set holdout
   ```

3. Better still, add your own labelled queries to `benchmarks/extraction_cases.py`. A prompt tuned on the same queries it is scored on will look better than it is, so keep some queries back.
4. Use it: `Detector(fields, llm, prompt="my_prompt.txt")`.

A prompt that does better on a fresh set of queries is welcome as a pull request (as `v3.txt`, with its benchmark numbers).
