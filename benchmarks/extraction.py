"""Extraction accuracy: does the LLM turn each labelled query into the right filters?

    OPENROUTER_API_KEY=... uv run python benchmarks/extraction.py [--model anthropic/claude-haiku-4.5]

Calls the LLM once per case (30 cases). Scores the filters (time ranges, people,
sort) as an exact match per case, and list_only separately. An end date after
today counts as open-ended ("this week" may end next Monday or stay open). Prints a table and
the failures, and writes a JSON result next to this script.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.request
from datetime import date
from pathlib import Path

from extraction_cases import CASES, FRESH, HOLDOUT, TODAY

from whowhen_rag import Field
from whowhen_rag.extract import build_prompt, load_prompt, parse_answer

FIELDS = [Field(r, role=r) for r in ("created_at", "updated_at", "created_by", "updated_by")]


def openrouter(model: str):
    key = os.environ["OPENROUTER_API_KEY"]

    def llm(prompt: str) -> str:
        body = json.dumps({"model": model, "temperature": 0, "max_tokens": 512,
                           "messages": [{"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body,
                                     headers={"Authorization": f"Bearer {key}",
                                              "Content-Type": "application/json"})
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
        return data["choices"][0]["message"]["content"] or ""

    llm.usage = []
    return llm


def end_ok(expected, got, today: str) -> bool:
    """An end date after today selects the same past documents as an open end."""
    return expected == got or (expected is None and got is not None and got > today)


def role_ok(expected: str, got: str) -> bool:
    return got in expected.split("|")


def check(case, ex) -> list[str]:
    _, times, people, sort, _ = case
    errors = []
    got_times = sorted((r, s.isoformat() if s else None, e.isoformat() if e else None) for r, s, e in ex.time_ranges)
    if len(got_times) != len(times) or not all(
        role_ok(er, gr) and es == gs and end_ok(ee, ge, TODAY)
        for (er, es, ee), (gr, gs, ge) in zip(sorted(times, key=str), sorted(got_times, key=str))
    ):
        errors.append(f"time: expected {times}, got {got_times}")
    if sorted(people) != sorted(ex.people):
        errors.append(f"people: expected {people}, got {ex.people}")
    if (sort is None) != (ex.sort is None) or (sort and not (role_ok(sort[0], ex.sort[0]) and sort[1] == ex.sort[1])):
        errors.append(f"sort: expected {sort}, got {ex.sort}")
    return errors


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="anthropic/claude-haiku-4.5")
    ap.add_argument("--set", choices=["main", "holdout", "fresh"], default="main")
    ap.add_argument("--prompt", default="v2", help="built-in prompt (v1, v2) or a path to your template")
    ap.add_argument("--label", default="", help="suffix for the result file; defaults to prompt-<name>")
    args = ap.parse_args()
    llm = openrouter(args.model)
    template = load_prompt(args.prompt)
    label = args.label or f"prompt-{Path(args.prompt).stem}"
    today = date.fromisoformat(TODAY)

    results, filters_ok, list_ok, seconds = [], 0, 0, []
    cases = {"main": CASES, "holdout": HOLDOUT, "fresh": FRESH}[args.set]
    for case in cases:
        t0 = time.perf_counter()
        ex = parse_answer(llm(build_prompt(case[0], FIELDS, today, template)), FIELDS)
        seconds.append(time.perf_counter() - t0)
        errors = check(case, ex)
        lo = ex.list_only == case[4]
        filters_ok += not errors
        list_ok += lo
        results.append({"query": case[0], "filters_ok": not errors, "errors": errors,
                        "list_only_ok": lo, "list_only": ex.list_only, "cleaned_query": ex.cleaned_query})
        print(f"{'OK ' if not errors else 'BAD'} {'   ' if lo else 'LO!'} {case[0]}")
        for e in errors:
            print(f"        {e}")

    n = len(cases)
    tokens_in = sum(u.get("prompt_tokens", 0) for u in llm.usage)
    tokens_out = sum(u.get("completion_tokens", 0) for u in llm.usage)
    seconds.sort()
    summary = {
        "date": date.today().isoformat(),
        "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], check=False, capture_output=True, text=True).stdout.strip(),
        "model": args.model, "set": args.set, "prompt": args.prompt, "label": label, "cases": n,
        "filters_exact": filters_ok, "list_only_correct": list_ok,
        "avg_prompt_tokens": round(tokens_in / n), "avg_completion_tokens": round(tokens_out / n),
        "median_seconds": round(seconds[n // 2], 2),
    }
    print(f"\nfilters exact: {filters_ok}/{n}   list_only: {list_ok}/{n}   "
          f"tokens per call: {summary['avg_prompt_tokens']} in / {summary['avg_completion_tokens']} out   "
          f"median {summary['median_seconds']}s")
    suffix = f"_{label}"
    name = f"{summary['date']}_extraction_{args.model.split('/')[-1]}_{args.set}{suffix}.json"
    out = Path(__file__).parent / "results" / name
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "results": results}, indent=2))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
