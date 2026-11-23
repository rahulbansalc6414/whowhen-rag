# Benchmark results

Append new runs; do not overwrite. All queries are synthetic and labelled in `benchmarks/cases.py` (until 2026-11-22 the gate questions lived in `tests/queries.py` and the extraction questions in `benchmarks/extraction_cases.py`, scored by the retired `gates.py` and `extraction.py`).
Raw per-query output for every run is in `results/`.

## Single benchmark (`benchmarks/run.py`, from 2026-11-22)

All 119 labelled questions (81 need a filter, 37 plain, 1 either) take the real path: regex, Jev only where the design calls it, the LLM only when a gate says yes. Today fixed at 2026-11-18. "Pipeline" = what the user gets is fully right.

| Date | Commit | Design | Model | Prompt | Pipeline | LLM right / called | Recency found | Jev median | LLM median | Cost per extraction |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-11-22 | b2bb4e6 + uncommitted | LLM does recency (sort) | Haiku 4.5 | v2 | 112/119 | 82/89 | 11/16 (by the LLM) | 298 ms | 1430 ms | 0.11 cents |
| 2026-11-23 | uncommitted | recency from Jev (p >= 0.95), Jev filter gate p >= 0.6 | Haiku 4.5 | v4 | **114/119** | 86/89 | 16/16 | 294 ms | 1270 ms | 0.11 cents |
| 2026-11-23 | uncommitted | same | **Haiku 5.5, thinking off** | v4 | **113/119** | 85/89 | 16/16 | 298 ms | **949 ms** | **0.013 cents** |

Gates in every run: regex caught 72/81 filter questions; Jev said yes to all 9 the regex missed (confidence 0.68 to 1.00) and no to 30 of 32 plain ones; no filter question was stopped. The 7 plain questions let through (5 "who wrote/owns/updated X?" by the regex, 2 by Jev at 0.84 to 0.89) all came back as no filter.

v2 run misses: 5 of 7 were recency. Haiku 4.5 invented windows ("updated recently" became the last 2 weeks, "these days" 7 days, "what's new" today only) and chose created or updated for "latest" inconsistently. Plus "since September" in 2025 and created vs updated for "added ... since August".

v4 runs, misses beyond two shared recency extras from Jev ("anything new on the search project since Monday", "any new incident reports today?", both at 0.99 to 1.00 and arguably recency):
- Haiku 4.5: "since September" in 2025 (a wrong filter that hides the right documents); "added to the API guide since August" as created (arguable); "over the summer" ending 2026-09-21 (label allowed 09-22 or 09-23; arguable).
- Haiku 5.5: "design docs updated since December" and "meeting notes from Q3" returned no filter (the filter is dropped, so the user gets a broader search: a safe failure); "added ... since August" as created and "most recent docs by Aiko" as edited by rather than created by (both arguable).
- Question by question, the models differ on 5: Haiku 4.5 alone got "since December", "Q3" and "docs by Aiko" right; Haiku 5.5 alone got "since September" and "over the summer" right. On the three periods without a year, 4.5 was right on 2 (wrong year on the third), 5.5 on 1 (no filter on the other two). The "summer" label allows an end of 09-01, 09-22 or 09-23 but not 4.5's 09-21 (the astronomical end of summer); a looser label would put 4.5 at 115.

Decision: ship with Haiku 5.5 (thinking off) as the tested model. Accuracy within one or two questions of 4.5, its misses here fall back to an ordinary search rather than a wrong filter, about 25% faster, about 8 times cheaper, and the current Haiku (4.5 is legacy). A cost and speed choice more than an accuracy one; "a period without a year" is the weakness to target in a v5 prompt.

Supporting checks, 2026-11-23:
- Haiku 5.5 on the 7 questions Haiku 4.5 missed under v2: 3/7 with thinking on or off; thinking off was faster (about 1.1 s) and used fewer tokens.
- Jev recency trial on all 119 (`results/2026-11-23_jev_recency_trial.json`): 16/16 recency questions at 0.99 to 1.00; no plain question marked; extras on 17 date-range questions at p >= 0.5, 4 at p >= 0.9, 2 at p >= 0.95. Asking the filter and recency questions in one Jev call took the same time as one question (median 293 ms).
- Jev threshold moved from > 0.5 to >= 0.6: no question in the v2 run changes route (lowest real filter question 0.68; "Marco's opinion" at 0.50 now clearly below).

## Gates (`benchmarks/gates.py`)

| Date | Commit | Classifier | Time (20) | Author (12) | Unusual wording (8) | Plain, no filter (20) |
|---|---|---|---|---|---|---|
| 2026-11-20 | cb236e2 | off | 20/20 regex | 12/12 regex | 0/8 | 20/20 stopped |
| 2026-11-20 | cb236e2 | Jev (threshold 0.5) | 20/20 regex | 12/12 regex | 8/8 Jev yes | 20/20 Jev no |

The regex patterns and these queries were written together, so the regex rows show coverage, not accuracy on unseen wording. Jev is the independent check: it never saw the query set.

## Extraction (`benchmarks/extraction.py`, Claude Haiku 4.5 via OpenRouter, temperature 0)

"Exact" = time ranges, people and sort all correct. An end date after today counts as open-ended.

| Date | Commit | Prompt | Set | Exact | list_only | Tokens in / out per call | Median latency |
|---|---|---|---|---|---|---|---|
| 2026-11-20 | cb236e2 | v1 | main (30) | 26/30 | 27/30 | 544 / 76 | 1.23 s |
| 2026-11-21 | cb236e2 | v1 | holdout (15) | 11/15 | 13/15 | 545 / 80 | 1.78 s |
| 2026-11-21 | a7d1ba0 | v2 | main (30) | 30/30 | 29/30 | 748 / 74 | 1.56 s |
| 2026-11-21 | a7d1ba0 | v2 | holdout (15) | 15/15 | 15/15 | 749 / 77 | 1.63 s |
| 2026-11-22 | b465710 | v2 | **fresh (15)** | **13/15** | 15/15 | 749 / 77 | 1.58 s |
| 2026-11-22 | uncommitted (v3 trial) | v2 | **fresh2 (15)** | **13/15** | 14/15 | 748 / 75 | 1.76 s |
| 2026-11-22 | uncommitted (v3 trial) | v3 | main (30) | 28/30 | 29/30 | 872 / 74 | 1.51 s |
| 2026-11-22 | uncommitted (v3 trial) | v3 | holdout (15) | 14/15 | 15/15 | 872 / 77 | 1.46 s |
| 2026-11-22 | uncommitted (v3 trial) | v3 | fresh (15) | 14/15 | 15/15 | 872 / 76 | 1.82 s |
| 2026-11-22 | uncommitted (v3 trial) | v3 | **fresh2 (15)** | **14/15** | 14/15 | 871 / 74 | 1.37 s |

Prompt v1 failures: a month without a year read as last year ("in October" -> 2025), "last month" read as the last 30 days, a year in a topic name read as a filter ("the 2025 pricing model", "2026 hiring plan"), a sort added when none was asked, and "past two weeks" ending at today (which drops today's documents).
Prompt v2 adds a rule for each of these. The holdout set was written before v2, but its v1 failures were seen while writing v2, so the v2 holdout score is not a clean held-out measurement.

The **fresh** set (15 queries) was written and labelled after v2 was final and run once, with no prompt change afterwards: the clean measurement for v2 is **13/15**. Failures: "since September" read as September 2025 (the month-without-a-year rule does not hold for "since"), and "what is Marco's opinion on the caching proposal" given a filter on documents by Marco (labelled no filter; arguable). Candidates for a v3, to be scored on another fresh set.

**v3 trial (2026-11-22).** The fresh2 set was written and labelled before v3 existed (case file sha256 `97cd6800...` at 09:59 UTC, before v3 was written). v3 added two rules to v2: a month without a year resolves to the latest one that has started after any word ("since", "before", ...), and a person's opinion, position, role or decision is not a filter on their documents. Its examples deliberately use other months and wording than the test sets.
Result: v3 70/75 vs v2 71/75 over all four sets; on the clean fresh2 set v3 14/15 vs v2 13/15. The person rule fixed "Tomas think" and "Marco's opinion" but overcorrected ("Priya's notes on the vendor review" lost its person filter). The month rule did not hold: "since September" still went to 2025, and "in October", correct under v2, went to 2025 too. "since Monday" came back a day late. Single runs, so differences of one or two may be noise. v3 not adopted; v2 stays the default. The month-to-year choice is the error no prompt version has removed.

On 2026-11-21 the prompts moved from code into `src/whowhen_rag/prompts/v1.txt` and `v2.txt`. A check confirmed both produce byte-for-byte the same text as the versions measured above, so these numbers apply to the files. Run `benchmarks/extraction.py --prompt v1|v2|<file>` to reproduce.

Cost at list price (Haiku 4.5: $1 / MTok input, $5 / MTok output): about 0.11 cents per extraction, about 110 cents ($1.10) per 1,000 queries that reach the LLM.
