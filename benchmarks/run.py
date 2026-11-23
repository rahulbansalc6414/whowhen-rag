"""The single benchmark: every labelled question goes through whowhen-rag's Detector.

    TYPESAFE_API_KEY=... OPENROUTER_API_KEY=... uv run python benchmarks/run.py \
        [--model anthropic/claude-haiku-5.5] [--prompt v4] [--fix-years]

Each question in benchmarks/cases.py (today fixed at 2026-11-18) takes the real path:
  regex hit:  the LLM (dates, people) and Jev's recency question run in parallel
  regex miss: one Jev call (needs a filter? newest/oldest?), then the LLM if Jev says yes
The result is compared with the label: dates and people from the LLM, recency from Jev.
The report shows what each step caught and missed, with Jev's confidence and every
latency, and every row is saved to benchmarks/results/<date>_run_<label>.json.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import time
import urllib.request
from datetime import date
from pathlib import Path

from cases import ALL, ALTERNATIVES, TODAY

from whowhen_rag import Detector, Field, JevClassifier

FIELDS = [Field(r, role=r) for r in ("created_at", "updated_at", "created_by", "updated_by")]
# List price per million tokens (input, output), from Anthropic's model pages.
PRICES = {"anthropic/claude-haiku-5.5": (0.10, 0.50), "anthropic/claude-haiku-4.5": (1.0, 5.0)}


# --- LLM ------------------------------------------------------------------------

def openrouter(model: str):
    """Your-LLM function for the Detector. Haiku 5.x: thinking off, no temperature."""
    key = os.environ["OPENROUTER_API_KEY"]
    body_base = {"model": model, "max_tokens": 1024}
    if "haiku-4" in model:
        body_base["temperature"] = 0
    else:
        body_base["reasoning"] = {"enabled": False}

    def llm(prompt: str) -> str:
        body = json.dumps({**body_base, "messages": [{"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body,
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = json.load(r)
                break
            except (OSError, ValueError):
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
        llm.usage.append(data.get("usage", {}))
        return data["choices"][0]["message"].get("content") or ""

    llm.usage = []
    return llm


# --- scoring --------------------------------------------------------------------

def _ok(spec, got) -> bool:
    """Does a value match a label spec? Specs: None, "a", "a|b"; "open" in a date spec means no end."""
    if spec is None:
        return got is None
    options = [o.lower() for o in spec.split("|")]
    if got is None:
        return "open" in options
    return str(got).lower() in options


def _ok_end(spec, got) -> bool:
    # An end after today selects the same past documents as an open end.
    if (spec is None or "open" in spec.split("|")) and (got is None or got > TODAY):
        return True
    return spec is not None and _ok(spec, got)


def _match_lists(expected, got, fields_ok) -> bool:
    if len(expected) != len(got):
        return False
    remaining = list(got)
    for e in expected:
        hit = next((g for g in remaining if fields_ok(e, g)), None)
        if hit is None:
            return False
        remaining.remove(hit)
    return True


def from_conditions(f):
    """Turn conditions back into (role, start, end) ranges and (role, name) people.

    The benchmark's columns are named after the roles, so a column is its role.
    """
    ranges: dict[str, list] = {}
    people = []
    for c in f.conditions:
        if c.op in (">=", "<"):
            r = ranges.setdefault(c.column, [None, None])
            r[0 if c.op == ">=" else 1] = c.value
        elif c.op == "=":
            people.append((c.column, c.value))
        else:
            people.extend((c.column, v) for v in c.value)
    return [(role, s, e) for role, (s, e) in ranges.items()], people


def filters_match(expect, f) -> bool:
    times, people, _, _ = expect
    got_times, got_people = from_conditions(f)
    return (_match_lists(times, got_times, lambda e, g: _ok(e[0], g[0]) and _ok(e[1], g[1]) and _ok_end(e[2], g[2]))
            and _match_lists(people, got_people, lambda e, g: _ok(e[0], g[0]) and _ok(e[1], g[1])))


def expected_recency(expect):
    return expect[2][1] if expect[2] else None


def describe_expect(expect) -> str:
    times, people, sort, _ = expect
    parts = [f"{r} {s or '...'} to {e or 'open'}" for r, s, e in times] + [f"{r}={n}" for r, n in people]
    if sort:
        parts.append(f"recency {sort[1]}")
    return "; ".join(parts) or "no filter"


def describe(f) -> str:
    times, people = from_conditions(f)
    parts = [f"{r} {s or '...'} to {e or 'open'}" for r, s, e in times] + [f"{r}={n}" for r, n in people]
    if f.recency:
        parts.append(f"recency {f.recency}")
    return "; ".join(parts) or "no filter"


# --- run ------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="anthropic/claude-haiku-5.5")
    ap.add_argument("--prompt", default="v4")
    ap.add_argument("--fix-years", action="store_true", help="turn on the experimental year check")
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    clf = JevClassifier()
    if not clf.enabled:
        raise SystemExit("TYPESAFE_API_KEY is required: the benchmark measures Jev")
    llm = openrouter(args.model)
    today = date.fromisoformat(TODAY)
    detector = Detector(FIELDS, llm, classifier=clf, today=lambda: today, prompt=args.prompt,
                        fix_years=args.fix_years)
    model_short = args.model.split("/")[-1]
    label = args.label or f"{model_short}_prompt-{Path(args.prompt).stem}{'_year-check' if args.fix_years else ''}"

    rows = []
    for i, (group, case) in enumerate(ALL, 1):
        query = case[0]
        expects = [case[1:]] + ALTERNATIVES.get(query, [])
        has_filter = [bool(e[0] or e[1] or e[2]) for e in expects]
        kind = "filter" if all(has_filter) else "none" if not any(has_filter) else "either"
        t0 = time.perf_counter()
        f = detector.detect(query)
        total_ms = round((time.perf_counter() - t0) * 1000)
        t = f.trace
        fok = [filters_match(e, f) for e in expects]
        rok = [expected_recency(e) == f.recency for e in expects]
        row = {
            "query": query, "group": group, "label": kind, "expected": describe_expect(expects[0]),
            "gate": t.gate, "jev_filter_p": t.jev_filter_p, "jev_recency_p": t.jev_recency_p,
            "recency": f.recency, "expected_recency": expected_recency(expects[0]),
            "jev_ms": t.jev_ms, "llm_called": t.llm_called, "llm_ms": t.llm_ms, "total_ms": total_ms,
            "got": describe(f), "year_fix": t.year_corrections, "error": t.error,
            "filters_ok": any(fok), "recency_ok": any(rok),
            "correct": any(a and b for a, b in zip(fok, rok)),
        }
        rows.append(row)
        jev = f"jev f={t.jev_filter_p}" if t.jev_filter_p is not None else "regex"
        print(f"{i:3} {'OK ' if row['correct'] else 'BAD'} {group:7} {jev:12} "
              f"{'LLM' if t.llm_called else '   '} {query}", flush=True)

    report(rows, args, label, llm.usage)


def _stats(xs) -> str:
    if not xs:
        return "n/a"
    xs = sorted(xs)
    return f"median {statistics.median(xs):.0f} ms, p90 {xs[max(0, int(len(xs) * 0.9) - 1)]:.0f} ms, max {xs[-1]} ms"


def report(rows, args, label, usage) -> None:
    need = [r for r in rows if r["label"] == "filter"]
    plain = [r for r in rows if r["label"] == "none"]

    print("\n=== Gates (does each question reach the LLM when it should?)")
    rx = [r for r in rows if r["gate"] == "regex"]
    print(f"regex: caught {sum(r['gate'] == 'regex' for r in need)}/{len(need)} questions that need a filter; "
          f"also caught {sum(r['gate'] == 'regex' for r in plain)}/{len(plain)} plain questions")
    for r in plain:
        if r["gate"] == "regex":
            print(f"    plain but regex hit: {r['query']}")
    jn = [r for r in need if r["jev_filter_p"] is not None]
    jp = [r for r in plain if r["jev_filter_p"] is not None]
    print(f"jev filter gate (on {len(jn) + len(jp)} regex misses, yes at p >= 0.6): "
          f"yes to {sum(r['gate'] == 'classifier' for r in jn)}/{len(jn)} that need a filter, "
          f"no to {sum(r['gate'] == 'none' for r in jp)}/{len(jp)} plain")
    for r in jn:
        if r["gate"] != "classifier":
            print(f"    MISSED (needs a filter) p={r['jev_filter_p']}: {r['query']}")
    for r in jp:
        if r["gate"] == "classifier":
            print(f"    false yes p={r['jev_filter_p']}: {r['query']}")

    print("\n=== Recency (Jev, every question; hint given at p >= 0.95)")
    want = [r for r in rows if r["expected_recency"]]
    print(f"found {sum(r['recency'] == r['expected_recency'] for r in want)}/{len(want)} questions asking for "
          f"newest or oldest")
    for r in want:
        if r["recency"] != r["expected_recency"]:
            print(f"    MISSED p={r['jev_recency_p']}: {r['query']} (expected {r['expected_recency']}, got {r['recency']})")
    extra = [r for r in rows if not r["expected_recency"] and r["recency"] and not r["recency_ok"]]
    print(f"hint given where none was expected: {len(extra)}")
    for r in extra:
        print(f"    {r['recency']} p={r['jev_recency_p']}: {r['query']}")

    print("\n=== LLM extraction (dates and people, only what the gates sent)")
    sent = [r for r in rows if r["llm_called"]]
    print(f"correct: {sum(r['filters_ok'] for r in sent)}/{len(sent)}")
    for r in sent:
        if not r["filters_ok"]:
            print(f"    WRONG [{r['group']}] {r['query']}\n        expected: {r['expected']}\n        got:      {r['got']}")
    if args.fix_years:
        fixes = [r for r in rows if r["year_fix"]]
        print(f"year check corrected {len(fixes)} answers")
        for r in fixes:
            print(f"    [{'OK' if r['filters_ok'] else 'BAD'}] {r['query']}: {'; '.join(r['year_fix'])}")

    print("\n=== Full pipeline (what a user gets: filters and recency both right)")
    total_ok = sum(r["correct"] for r in rows)
    print(f"correct: {total_ok}/{len(rows)}")
    groups: dict[str, list[int]] = {}
    for r in rows:
        g = groups.setdefault(r["group"], [0, 0])
        g[0] += r["correct"]
        g[1] += 1
    print("by group: " + ", ".join(f"{g} {ok}/{n}" for g, (ok, n) in groups.items()))
    for r in rows:
        if not r["correct"] and not r["llm_called"] and not r["filters_ok"]:
            print(f"    WRONG, stopped by the gates [{r['group']}] {r['query']} (expected: {r['expected']})")

    jev_ms = [r["jev_ms"] for r in rows if r["jev_ms"] is not None]
    llm_ms = [r["llm_ms"] for r in rows if r["llm_ms"] is not None]
    print("\n=== Latency and cost")
    print(f"jev: {len(jev_ms)} calls, {_stats(jev_ms)}")
    print(f"llm: {len(llm_ms)} calls, {_stats(llm_ms)}")
    print(f"detect() wall time, regex path (LLM and Jev in parallel): {_stats([r['total_ms'] for r in rx])}")
    print(f"detect() wall time, all questions: {_stats([r['total_ms'] for r in rows])}")
    tin = sum(u.get("prompt_tokens", 0) for u in usage)
    tout = sum(u.get("completion_tokens", 0) for u in usage)
    pin, pout = PRICES.get(args.model, (0, 0))
    cost_cents = (tin * pin + tout * pout) / 1e6 * 100
    print(f"extraction calls per 100 questions: {100 * len(llm_ms) / len(rows):.0f}; tokens {tin} in / {tout} out "
          f"({tin / max(1, len(llm_ms)):.0f} / {tout / max(1, len(llm_ms)):.0f} per call); list cost {cost_cents:.2f} "
          f"cents ({cost_cents / max(1, len(llm_ms)):.4f} cents per extraction)")

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], check=False, capture_output=True,
                            text=True).stdout.strip()
    summary = {
        "date": date.today().isoformat(), "commit": commit, "model": args.model, "prompt": args.prompt,
        "fix_years": args.fix_years, "questions": len(rows), "need_filter": len(need), "plain": len(plain),
        "pipeline_correct": total_ok, "llm_calls": len(sent), "llm_correct": sum(r["filters_ok"] for r in sent),
        "recency_found": sum(r["recency"] == r["expected_recency"] for r in want), "recency_expected": len(want),
        "recency_extra": len(extra), "jev_median_ms": statistics.median(jev_ms) if jev_ms else None,
        "llm_median_ms": statistics.median(llm_ms) if llm_ms else None,
        "tokens_in": tin, "tokens_out": tout, "cost_cents": round(cost_cents, 3),
    }
    out = Path(__file__).parent / "results" / f"{summary['date']}_run_{label}.json"
    out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    print(f"\nsaved {out}")


if __name__ == "__main__":
    main()
