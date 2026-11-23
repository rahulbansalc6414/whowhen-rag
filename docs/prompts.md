# Prompts

The extraction prompt is a plain text template in [`src/whowhen_rag/prompts/`](../src/whowhen_rag/prompts/). It is the only part of `whowhen-rag` that talks to your LLM, so it is the part most worth tuning.

| Version | File | Status |
|---|---|---|
| v1 | [`v1.txt`](../src/whowhen_rag/prompts/v1.txt) | first version, kept for comparison |
| v2 | [`v2.txt`](../src/whowhen_rag/prompts/v2.txt) | kept for comparison (asked the LLM for a sort; its `sort` answer is now ignored) |
| v3 | not shipped | tried two extra rules, did worse than v2 (see below) |
| v4 | [`v4.txt`](../src/whowhen_rag/prompts/v4.txt) | **default**: v2 without sorting; recency comes from Jev |

```python
Detector(fields, llm)                         # v4
Detector(fields, llm, prompt="v2")            # an older built-in version
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

Whatever the template says, the answer must be the JSON object v4 describes (`time_ranges`, `people`, `list_only`, `cleaned_query`): that is what `whowhen-rag` parses and validates. Any other key (such as v1 and v2's `sort`) is ignored.

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

The extra rules cost about 200 input tokens per call: about 0.02 cents more per extraction with Haiku 4.5. The held-out queries were written before v2, but their v1 failures were seen while writing v2, so the v2 held-out score is not a clean held-out measurement. Full history: [`benchmarks/RESULTS.md`](../benchmarks/RESULTS.md).

## v3: tried and not shipped

On 2026-11-22 a new set of 15 queries ("fresh2") was written before v3, then v3 added two rules to v2: a month without a year resolves to the latest one that has started after any word ("since", "before"...), and a person's opinion, position or role is not a filter on their documents. Its examples deliberately used other months and wording than the test sets.

| Prompt | main (30) | holdout (15) | fresh (15) | fresh2 (15) | Total |
|---|---|---|---|---|---|
| v2 | 30 | 15 | 13 | 13 | **71** |
| v3 | 28 | 14 | 14 | 14 | 70 |

The person rule fixed "what does Tomas think about..." but overcorrected ("Priya's notes on the vendor review" lost its person filter). The month rule did not hold: "since September" still went to 2025, and "in October", right under v2, went to 2025 too. Lesson: rewording a rule can move an error around instead of removing it.

## v4: recency moves to Jev

The first run of the single benchmark (all 119 questions through regex, Jev and the LLM) showed that 5 of v2's 7 misses were about recency. Asked for "security policies updated recently", Haiku 4.5 invented a two-week window; for "these days", seven days; for "what's new", today only. v2 said "sort only, no window", and the model ignored it. It also picked the created date or the updated date for "latest" seemingly at random.

Jev, asked "newest, oldest or neither?", found all 16 recency questions with 0.99 to 1.00 confidence. So v4 removes every sorting instruction from the prompt and adds one rule in its place: words that only ask for the newest or oldest material are never a time range. The LLM extracts only dates and people; the recency hint comes from Jev. Results are in [`benchmarks/RESULTS.md`](../benchmarks/RESULTS.md).

## Writing your own

1. Copy `src/whowhen_rag/prompts/v4.txt` and edit it: your domain's wording, another language, extra examples.
2. Score it with the benchmark (needs `TYPESAFE_API_KEY` and `OPENROUTER_API_KEY`; about 90 LLM calls, about 1 cent with Haiku 5.5):

   ```bash
   uv run python benchmarks/run.py --prompt my_prompt.txt
   ```

3. Better still, add your own labelled queries to `benchmarks/cases.py` first. A prompt tuned on the same queries it is scored on will look better than it is, so keep some queries back.
4. Use it: `Detector(fields, llm, prompt="my_prompt.txt")`.

A prompt that does better on a fresh set of queries is welcome as a pull request (as `v5.txt`, with its benchmark numbers).
