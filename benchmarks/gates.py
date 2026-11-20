"""How many queries reach the LLM? Runs the free and cheap gates over the synthetic set.

    uv run python benchmarks/gates.py                 # regex only
    TYPESAFE_API_KEY=... uv run python benchmarks/gates.py   # regex + Jev

No LLM is called. Prints, per query group, where each query stopped, and the
share of queries that would have gone to the LLM.
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

from queries import CLASSIFIER_ONLY, PLAIN, REGEX_AUTHOR, REGEX_TIME

from whowhen import Detector, Field

GROUPS = {
    "time (needs filter)": (REGEX_TIME, True),
    "author (needs filter)": (REGEX_AUTHOR, True),
    "unusual wording (needs filter)": (CLASSIFIER_ONLY, True),
    "plain (no filter)": (PLAIN, False),
}


def main() -> None:
    use_jev = bool(os.environ.get("TYPESAFE_API_KEY"))
    detector = Detector([Field("t", role="updated_at"), Field("p", role="created_by")],
                        llm=lambda p: "{}", use_classifier=use_jev)
    print(f"classifier: {'Jev' if use_jev else 'off (no TYPESAFE_API_KEY)'}\n")
    total = Counter()
    print(f"{'group':34} {'n':>3} {'regex':>6} {'clf yes':>8} {'none':>5} {'correct':>8}")
    for name, (queries, needs) in GROUPS.items():
        c = Counter(detector.gate(q).gate for q in queries)
        correct = (c["regex"] + c["classifier"]) if needs else c["none"]
        print(f"{name:34} {len(queries):3} {c['regex']:6} {c['classifier']:8} {c['none']:5} "
              f"{correct:5}/{len(queries)}")
        total.update(c)
        total["n"] += len(queries)
    to_llm = total["regex"] + total["classifier"]
    print(f"\nqueries reaching the LLM: {to_llm}/{total['n']} ({to_llm / total['n']:.0%})")


if __name__ == "__main__":
    main()
