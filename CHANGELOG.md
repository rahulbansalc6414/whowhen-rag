# Changelog

What changed in each release, and why. Benchmark details for every number here are in [`benchmarks/RESULTS.md`](benchmarks/RESULTS.md).

## 0.2.0 (2026-11-23)

**An upgrade on every measure: faster, about 8 times cheaper, more accurate, and it now gets every "latest" / "recent" question right.**

| | 0.1.0 | **0.2.0** |
|---|---|---|
| Recency questions ("latest", "recently", "these days", "what's new") | 11 of 16 right | **16 of 16** |
| Fully right on the 119-question benchmark | 112 | **113** (Haiku 5.5), 114 (Haiku 4.5) |
| Time per query (median) | about 1.4 s | **about 0.9 s** |
| Cost per extraction call | 0.11 cents | **0.013 cents** |

What changed: recency becomes a hint from Jev instead of a sort chosen by the LLM, the tested model moves to Claude Haiku 5.5, and one benchmark now measures the whole pipeline.

**Comparing with the 0.1.0 README.** 0.1.0's README quoted near-perfect scores (8 of 8, 20 of 20, 13 of 15) from two separate, smaller benchmarks: one checked only whether a question reached the LLM, the other only scored the LLM on questions with almost no vague recency wording. Neither could see the recency failures. Those numbers cannot be compared with 0.2.0's. The fair comparison is the table here and below: the 0.1.0 code and the 0.2.0 code on the same 119 questions, scored end to end on the final answer. On that test 0.1.0 scores 112 and 0.2.0 scores 113 to 114.

**Results on the 119-question benchmark** (the same questions for every row):

| | 0.1.0 design, Haiku 4.5 | 0.2.0, Haiku 4.5 | **0.2.0, Haiku 5.5** |
|---|---|---|---|
| Fully right | 112/119 | 114/119 | **113/119** |
| Recency questions handled right | 11/16 | 16/16 | 16/16 |
| Time per query (median) | about 1.4 s | about 1.25 s | **about 0.9 s** |
| Cost per extraction call | 0.11 cents | 0.11 cents | **0.013 cents** |

### Breaking changes

- **`f.sort`, `Sort` and `Filters.order_by_sql()` are removed.** Use `f.recency` instead: `"newest"`, `"oldest"` or `None`. It is a hint with no column attached; the README explains how to apply it (order your top relevance matches by your "last updated" date, rather than sorting the whole search by date).
- **Default prompt is now `v4`.** It extracts only dates and people. The old `v2` and `v1` are still available with `prompt="v2"`; their `sort` answer is now ignored.
- **Jev's filter gate now says yes when its confidence is 0.6 or more** (was: above 0.5). On the benchmark no question changed route; the margin is wider. Set `JevClassifier(threshold=...)` to change it.

### Why recency moved to Jev

The first full-pipeline benchmark showed that 5 of the LLM's 7 misses were about recency. Asked about "security policies updated recently", Haiku 4.5 invented a two-week window; for "these days", seven days; for "what's new", today only. It also chose the created date or the updated date for "latest" seemingly at random, so "latest deployment runbook" and "most up to date runbook" were sorted differently. Jev, asked "newest, oldest or neither?", found all 16 recency questions with 0.99 to 1.00 confidence and never marked a plain question.

### Why Haiku 5.5

Haiku 5.5 is the current Haiku (4.5 is a legacy model). On the benchmark it was within one question of Haiku 4.5 (113 vs 114), about 25% faster and about 8 times cheaper per extraction. The two miss different questions; Haiku 5.5's misses left the filter out (an ordinary search) rather than applying a wrong one. Run it with thinking off: in our tests thinking gave the same answers, slower and with more tokens. `whowhen-rag` does not include a model; this changes what we test with and what the README recommends.

### Added

- `f.recency`, from Jev. On a regex hit, Jev's recency question runs in parallel with your LLM, so a query takes no longer. On a regex miss, one Jev call answers both "needs a filter?" and "newest or oldest?". If Jev says no filter, the recency hint is still returned; if the LLM fails, the hint survives.
- `JevClassifier(recency_threshold=0.95)`: the hint is given only when Jev is at least this sure.
- `JevClassifier.judge()` and `Judgement`: ask Jev the filter and recency questions in one call.
- `f.trace` records Jev's filter and recency confidences, and Jev and LLM latencies.
- Experimental, off by default: `Detector(..., fix_years=True)` corrects the year when the LLM puts a month named without a year ("since September") in last year.
- README sections: "What 'recent' means", time zones, and an Anthropic example for Haiku 5.5 with thinking off.

### Benchmark

- One benchmark, `benchmarks/run.py`, replaces `gates.py` and `extraction.py`. All 119 labelled questions (`benchmarks/cases.py`) go through the real `Detector`; it reports what the regex, Jev and the LLM each caught and missed, Jev's confidence on every question, and every latency. Running the two parts separately had hidden the recency failures: those questions had only ever been checked for routing, never for the filters returned.
- Prompt v3 was tried and not shipped: on 75 questions it scored 70 against v2's 71, and its month rule made one case worse. See `docs/prompts.md`.
- The test suite now fails any test that tries to use the network.

## 0.1.0 (2026-11-22)

First release.

- Three steps: a free regex gate, the Jev classifier for queries the regex misses, and the caller's LLM only when a gate says yes.
- Caller-declared columns by role (`created_at`, `updated_at`, `created_by`, `updated_by`), name resolvers, date formats.
- Output as conditions, SQL, Chroma and Qdrant filters; prompts as versioned files (v1, v2).
- Measured with Claude Haiku 4.5: 13 of 15 exactly right on a fresh set written after prompt v2 was final.
