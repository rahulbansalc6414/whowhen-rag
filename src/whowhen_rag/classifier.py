"""Jev: the filter gate for queries the regex missed, and the recency hint.

Jev (TypeSafe System One) answers multiple-choice questions with calibrated
probabilities, far cheaper and faster than an LLM call. whowhen-rag asks it two
questions, in one call when both are needed:

- "filter": does the query limit documents by time or author? (gate 2, only when
  the regex missed)
- "recency": does it want the newest material, the oldest, or neither?

Jev cannot pull out dates or names; that is the LLM's job, and the LLM only runs
when a gate says yes.

Any function ``query -> bool`` can replace Jev as the filter gate (``Classifier``);
the recency hint needs an object with a ``judge`` method like JevClassifier's.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import ClassVar, Protocol

logger = logging.getLogger("whowhen_rag")

JEV_API_KEY_ENV = "TYPESAFE_API_KEY"


class Classifier(Protocol):
    def __call__(self, query: str) -> bool:
        """True if the query asks about when something happened or who made it."""
        ...


@dataclass
class Judgement:
    """Jev's answers for one query. A field is None when that question was not asked."""

    filter_p: float | None = None
    recency: str | None = None  # "newest", "oldest", or None
    recency_p: float | None = None  # probability of the most likely recency answer


class JevClassifier:
    """Filter gate and recency hint backed by Jev (``typesafe-sdk``).

    Args:
        api_key: Jev API key. Defaults to the ``TYPESAFE_API_KEY`` environment variable.
        threshold: The query needs a filter when the probability of "filter" is at least
            this (default 0.6).
        recency_threshold: The recency hint is "newest" or "oldest" only when Jev's
            probability for it is at least this (default 0.95); otherwise it is None.
        model: Optional Jev model override.

    Without a key it logs one warning and answers "no filter" and "no recency" for
    every query, so only the regex gate is active. A failed call gives the same
    answers: a classifier failure must never break search.
    """

    QUESTION: ClassVar[str] = (
        "Does this query ask about WHEN documents were created or changed, or WHO created or edited them?"
    )
    CRITERIA: ClassVar[dict[str, str]] = {
        "filter": (
            "The query limits or sorts documents by a date, a period, recency, or the person who "
            "wrote, created, edited or owns them"
        ),
        "plain": "The query asks about a topic only, with no condition on dates, recency or authorship",
    }
    RECENCY_QUESTION: ClassVar[str] = (
        "Does this search query ask for the newest material, the oldest material, or neither?"
    )
    RECENCY_CRITERIA: ClassVar[dict[str, str]] = {
        "newest": (
            "Wants the latest, newest, most recent, up to date or fresh material, or asks what is new, "
            "what changed recently or what has been going on lately"
        ),
        "oldest": "Wants the oldest, earliest, first or original material",
        "neither": (
            "No preference for newer or older material: a plain topic question, or a question that "
            "names a specific period (yesterday, last week, in March) without asking for the newest"
        ),
    }

    def __init__(
        self,
        api_key: str | None = None,
        threshold: float = 0.6,
        recency_threshold: float = 0.95,
        model: str | None = None,
    ) -> None:
        self.api_key = (api_key if api_key is not None else os.environ.get(JEV_API_KEY_ENV, "")).strip()
        self.threshold = threshold
        self.recency_threshold = recency_threshold
        self.model = model
        self._client = None
        if not self.api_key:
            logger.warning(
                "whowhen-rag: no Jev API key (set %s or pass JevClassifier(api_key=...)); the classifier "
                "and the recency hint are off and only the regex gate is active. Pass use_classifier=False "
                "to silence this.",
                JEV_API_KEY_ENV,
            )

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        if self._client is None:
            from typesafe_sdk import TypeSafeClient

            self._client = TypeSafeClient(api_key=self.api_key)
        return self._client

    def judge(self, query: str, *, ask_filter: bool = True, ask_recency: bool = True) -> Judgement:
        """Ask Jev the chosen questions in one call. Returns empty answers if off or on failure."""
        out = Judgement()
        if not self.enabled or not (ask_filter or ask_recency):
            return out
        try:
            from typesafe_sdk import Choice

            questions = {}
            if ask_filter:
                questions["intent"] = Choice(instructions=self.QUESTION, criteria=self.CRITERIA)
            if ask_recency:
                questions["recency"] = Choice(instructions=self.RECENCY_QUESTION, criteria=self.RECENCY_CRITERIA)
            kwargs = {"model": self.model} if self.model else {}
            response = self._get_client().system_one(
                state=f"A user's search query to a document knowledge base: {query}",
                questions=questions,
                **kwargs,
            )
            if ask_filter:
                out.filter_p = float(response.answers["intent"].probabilities.get("filter", 0.0))
            if ask_recency:
                probs = response.answers["recency"].probabilities
                best = max(probs, key=probs.get)
                out.recency_p = float(probs[best])
                if best in ("newest", "oldest") and out.recency_p >= self.recency_threshold:
                    out.recency = best
        except Exception:
            logger.warning("whowhen-rag: Jev call failed; treating the query as needing no filter or recency",
                           exc_info=True)
            return Judgement()
        return out

    def probability(self, query: str) -> float | None:
        """Probability that the query needs a filter, or None if the classifier is off or failed."""
        return self.judge(query, ask_recency=False).filter_p

    def __call__(self, query: str) -> bool:
        p = self.probability(query)
        return p is not None and p >= self.threshold
