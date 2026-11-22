"""Detector: regex gate -> classifier gate -> your LLM, only when a filter is likely."""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime, timezone

from .classifier import Classifier, JevClassifier
from .extract import DEFAULT_PROMPT, ExtractionError, build_prompt, load_prompt, parse_answer
from .fields import Field
from .filters import Condition, Filters, Sort, Trace
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
            a gate finds a likely filter. Tested with Claude Haiku 4.5; any model that
            follows JSON instructions works.
        use_classifier: Run the yes/no classifier on queries the regex misses (default True).
        classifier: A custom classifier. Defaults to JevClassifier(), which reads
            TYPESAFE_API_KEY from the environment.
        today: Returns today's date for relative periods ("last week"). Defaults to UTC today.
        prompt: The extraction prompt: a built-in version ("v2", the default, or "v1"), a path to
            your own template file, or the template text. See docs/prompts.md.

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

    # --- gates ----------------------------------------------------------------

    def gate(self, query: str) -> Trace:
        """Run only the cheap gates (regex, then classifier). Never calls the LLM."""
        trace = Trace()
        if regex_signal(query):
            trace.gate = "regex"
        elif self.classifier is not None:
            trace.classifier_called = True
            if self.classifier(query):
                trace.gate = "classifier"
        return trace

    def has_signal(self, query: str) -> bool:
        """True if a gate thinks the query has a time or author condition."""
        return self.gate(query).gate != "none"

    # --- full detection --------------------------------------------------------

    def detect(self, query: str) -> Filters:
        """Return the filters for a query. Never raises for model failures: they give no filter."""
        query = (query or "").strip()
        trace = self.gate(query) if query else Trace()
        if trace.gate == "none":
            return Filters(cleaned_query=query, trace=trace)

        trace.llm_called = True
        try:
            answer = self.llm(build_prompt(query, self.fields, self._today(), self.prompt_template))
            extraction = parse_answer(answer, self.fields)
        except ExtractionError as e:
            logger.warning("whowhen-rag: could not parse the LLM answer, no filter applied: %s", e)
            trace.error = str(e)
            return Filters(cleaned_query=query, trace=trace)
        except Exception as e:
            logger.warning("whowhen-rag: LLM call failed, no filter applied", exc_info=True)
            trace.error = f"{type(e).__name__}: {e}"
            return Filters(cleaned_query=query, trace=trace)

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

        sort = None
        if extraction.sort is not None:
            role, order = extraction.sort
            sort = Sort(self._by_role[role].column, descending=(order == "newest"))

        list_only = extraction.list_only and bool(conditions or sort)
        if list_only:
            cleaned = ""
        else:
            cleaned = extraction.cleaned_query or query
        if not (conditions or sort):
            cleaned = query
        return Filters(conditions=conditions, sort=sort, list_only=list_only, cleaned_query=cleaned, trace=trace)

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
