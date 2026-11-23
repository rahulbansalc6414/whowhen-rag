"""Detector: regex gate -> Jev -> your LLM, only when a filter is likely.

Paths through detect():
- regex hit: your LLM (dates, people) and Jev's recency question run in parallel.
- regex miss: one Jev call answers both "needs a filter?" and "newest/oldest?". If it
  needs a filter, your LLM runs next. Otherwise "no filter" is returned, with the
  recency hint if Jev gave one.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone

from .classifier import Classifier, JevClassifier, Judgement
from .dates import fix_month_years
from .extract import DEFAULT_PROMPT, ExtractionError, build_prompt, load_prompt, parse_answer
from .fields import Field
from .filters import Condition, Filters, Trace
from .gates import regex_signal

logger = logging.getLogger("whowhen_rag")

LLM = Callable[[str], str]


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


class Detector:
    """Find time and author filters in search queries.

    Args:
        fields: Your filterable columns and what they mean. At most one field per role.
        llm: Your LLM as a function: prompt text in, answer text out. Called only when
            a gate finds a likely filter. Tested with Claude Haiku 5.5 (thinking off) and
            Haiku 4.5; any model that follows JSON instructions works.
        use_classifier: Use Jev: the filter gate for queries the regex misses, and the
            recency hint (default True). Without it there is no recency hint.
        classifier: A custom classifier. Defaults to JevClassifier(), which reads
            TYPESAFE_API_KEY from the environment. A plain function ``query -> bool``
            works as the filter gate but gives no recency hint.
        today: Returns today's date for relative periods ("last week"). Defaults to UTC today.
        prompt: The extraction prompt: a built-in version ("v4", the default, or the older
            "v2", "v1"), a path to your own template file, or the template text. See docs/prompts.md.
        fix_years: Experimental, off by default. Correct the year when the LLM puts a month
            named without a year ("since September") in the wrong year. See dates.py.

    Example:
        >>> detector = Detector(
        ...     fields=[Field("modified_on", role="updated_at"), Field("owner", role="created_by")],
        ...     llm=my_llm,
        ... )
        >>> f = detector.detect("what did Priya write last week?")
        >>> where, params = f.to_sql()
    """

    def __init__(
        self,
        fields: list[Field],
        llm: LLM,
        *,
        use_classifier: bool = True,
        classifier: Classifier | None = None,
        today: Callable[[], date] | None = None,
        prompt: str = DEFAULT_PROMPT,
        fix_years: bool = False,
    ) -> None:
        if not fields:
            raise ValueError("Declare at least one Field")
        roles = [f.role for f in fields]
        duplicates = {r for r in roles if roles.count(r) > 1}
        if duplicates:
            raise ValueError(f"One field per role; repeated: {sorted(duplicates)}")
        if not callable(llm):
            raise TypeError("llm must be a function that takes a prompt string and returns a string")
        self.fields = list(fields)
        self._by_role = {f.role: f for f in fields}
        self.llm = llm
        self.classifier: Classifier | None = None
        if use_classifier:
            self.classifier = classifier if classifier is not None else JevClassifier()
        self._today = today or _utc_today
        self.prompt_template = load_prompt(prompt)
        self.fix_years = fix_years

    # --- Jev ------------------------------------------------------------------

    def _judge(self, query: str, *, ask_filter: bool, ask_recency: bool) -> tuple[Judgement, bool, int | None]:
        """Ask the classifier. Returns (answers, needs_filter, milliseconds)."""
        clf = self.classifier
        if clf is None:
            return Judgement(), False, None
        t0 = time.perf_counter()
        if hasattr(clf, "judge"):
            j = clf.judge(query, ask_filter=ask_filter, ask_recency=ask_recency)
            yes = j.filter_p is not None and j.filter_p >= getattr(clf, "threshold", 0.6)
        elif ask_filter:
            yes = bool(clf(query))
            j = Judgement(filter_p=1.0 if yes else 0.0)
        else:
            return Judgement(), False, None
        return j, yes, round((time.perf_counter() - t0) * 1000)

    # --- gates ----------------------------------------------------------------

    def gate(self, query: str) -> Trace:
        """Run only the cheap gates (regex, then Jev's filter question). Never calls the LLM."""
        trace = Trace()
        if regex_signal(query):
            trace.gate = "regex"
        elif self.classifier is not None:
            trace.classifier_called = True
            j, yes, trace.jev_ms = self._judge(query, ask_filter=True, ask_recency=False)
            trace.jev_filter_p = j.filter_p
            if yes:
                trace.gate = "classifier"
        return trace

    def has_signal(self, query: str) -> bool:
        """True if a gate thinks the query has a time or author condition."""
        return self.gate(query).gate != "none"

    # --- full detection --------------------------------------------------------

    def detect(self, query: str) -> Filters:
        """Return the filters for a query. Never raises for model failures: they give no filter."""
        query = (query or "").strip()
        trace = Trace()
        if not query:
            return Filters(trace=trace)

        recency = None
        if regex_signal(query):
            trace.gate = "regex"
            if self.classifier is not None and hasattr(self.classifier, "judge"):
                # Jev's recency question runs while the LLM extracts dates and people.
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(self._judge, query, ask_filter=False, ask_recency=True)
                    extraction, error = self._extract(query, trace)
                    j, _, trace.jev_ms = future.result()
                trace.classifier_called = True
                trace.jev_recency_p, recency = j.recency_p, j.recency
            else:
                extraction, error = self._extract(query, trace)
        else:
            if self.classifier is None:
                return Filters(cleaned_query=query, trace=trace)
            trace.classifier_called = True
            j, yes, trace.jev_ms = self._judge(query, ask_filter=True, ask_recency=True)
            trace.jev_filter_p, trace.jev_recency_p, recency = j.filter_p, j.recency_p, j.recency
            if not yes:
                return Filters(recency=recency, cleaned_query=query, trace=trace)
            trace.gate = "classifier"
            extraction, error = self._extract(query, trace)

        if error:
            return Filters(recency=recency, cleaned_query=query, trace=trace)

        conditions: list[Condition] = []
        for role, start, end in extraction.time_ranges:
            f = self._by_role[role]
            if start is not None:
                conditions.append(Condition(f.column, ">=", f.format_date(start)))
            if end is not None:
                conditions.append(Condition(f.column, "<", f.format_date(end)))

        names_by_role: dict[str, list[str]] = {}
        for role, name in extraction.people:
            names_by_role.setdefault(role, []).append(name)
        for role, names in names_by_role.items():
            f = self._by_role[role]
            values: list = []
            for name in names:
                value = self._resolve(f, name)
                if value is None:
                    trace.unresolved_people.append(name)
                elif isinstance(value, (list, tuple, set)):
                    values.extend(value)
                else:
                    values.append(value)
            values = list(dict.fromkeys(values))
            if len(values) == 1:
                conditions.append(Condition(f.column, "=", values[0]))
            elif values:
                conditions.append(Condition(f.column, "in", values))

        list_only = extraction.list_only and bool(conditions or recency)
        if list_only:
            cleaned = ""
        elif conditions or recency:
            cleaned = extraction.cleaned_query or query
        else:
            cleaned = query
        return Filters(conditions=conditions, recency=recency, list_only=list_only, cleaned_query=cleaned,
                       trace=trace)

    def _extract(self, query: str, trace: Trace):
        """Call the LLM. Returns (extraction, error); never raises."""
        trace.llm_called = True
        t0 = time.perf_counter()
        try:
            today = self._today()
            answer = self.llm(build_prompt(query, self.fields, today, self.prompt_template))
            extraction = parse_answer(answer, self.fields)
            if self.fix_years:
                trace.year_corrections = fix_month_years(query, extraction, today)
            return extraction, None
        except ExtractionError as e:
            logger.warning("whowhen-rag: could not parse the LLM answer, no filter applied: %s", e)
            trace.error = str(e)
        except Exception as e:
            logger.warning("whowhen-rag: LLM call failed, no filter applied", exc_info=True)
            trace.error = f"{type(e).__name__}: {e}"
        finally:
            trace.llm_ms = round((time.perf_counter() - t0) * 1000)
        return None, trace.error

    @staticmethod
    def _resolve(f: Field, name: str):
        if f.resolve is None:
            return name
        try:
            return f.resolve(name)
        except Exception:
            logger.warning("whowhen-rag: resolver for %r failed on %r; person filter dropped", f.column, name,
                           exc_info=True)
            return None
