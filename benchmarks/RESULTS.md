# Benchmark results

Append new runs; do not overwrite. All queries are synthetic (`tests/queries.py`, `benchmarks/extraction_cases.py`).
Raw per-query output for extraction runs is in `results/`.

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
| 2026-11-22 | 3c49aac + fresh set | v2 | **fresh (15)** | **13/15** | 15/15 | 749 / 77 | 1.58 s |

Prompt v1 failures: a month without a year read as last year ("in October" -> 2025), "last month" read as the last 30 days, a year in a topic name read as a filter ("the 2025 pricing model", "2026 hiring plan"), a sort added when none was asked, and "past two weeks" ending at today (which drops today's documents).
Prompt v2 adds a rule for each of these. The holdout set was written before v2, but its v1 failures were seen while writing v2, so the v2 holdout score is not a clean held-out measurement.

The **fresh** set (15 queries) was written and labelled after v2 was final and run once, with no prompt change afterwards: the clean measurement for v2 is **13/15**. Failures: "since September" read as September 2025 (the month-without-a-year rule does not hold for "since"), and "what is Marco's opinion on the caching proposal" given a filter on documents by Marco (labelled no filter; arguable). Candidates for a v3, to be scored on another fresh set.

On 2026-11-21 the prompts moved from code into `src/whowhen/prompts/v1.txt` and `v2.txt`. A check confirmed both produce byte-for-byte the same text as the versions measured above, so these numbers apply to the files. Run `benchmarks/extraction.py --prompt v1|v2|<file>` to reproduce.

Cost at list price (Haiku 4.5: $1 / MTok input, $5 / MTok output): about $0.0011 per extraction, about $1.10 per 1,000 queries that reach the LLM.
