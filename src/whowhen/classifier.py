"""Gate 2: a yes/no classifier for queries the regex missed.

The default is Jev (TypeSafe System One), which answers a multiple-choice
question with calibrated probabilities. It is far cheaper and faster than an
LLM call, but it only says yes or no: it cannot pull out the dates or names.
That is the extraction step's job, and it only runs when a gate says yes.

Any object with ``__call__(query: str) -> bool`` can replace it.
"""
from __future__ import annotations

import logging
import os
from typing import ClassVar, Protocol

logger = logging.getLogger("whowhen")

JEV_API_KEY_ENV = "TYPESAFE_API_KEY"


class Classifier(Protocol):
    def __call__(self, query: str) -> bool:
        """True if the query asks about when something happened or who made it."""
        ...


class JevClassifier:
    """Yes/no classifier backed by Jev (``typesafe-sdk``).

    Args:
        api_key: Jev API key. Defaults to the ``TYPESAFE_API_KEY`` environment variable.
        threshold: Probability of "filter" above which the answer is yes.
        model: Optional Jev model override.

    Without a key the classifier logs one warning and answers no for every
    query, so only the regex gate is active. Errors on a call also answer no:
    a classifier failure must never break search.
    """

    QUESTION: ClassVar[str] = "Does this query ask about WHEN documents were created or changed, or WHO created or edited them?"
    CRITERIA: ClassVar[dict[str, str]] = {
        "filter": (
            "The query limits or sorts documents by a date, a period, recency, or the person who "
            "wrote, created, edited or owns them"
        ),
        "plain": "The query asks about a topic only, with no condition on dates, recency or authorship",
    }

    def __init__(self, api_key: str | None = None, threshold: float = 0.5, model: str | None = None) -> None:
        self.api_key = (api_key if api_key is not None else os.environ.get(JEV_API_KEY_ENV, "")).strip()
        self.threshold = threshold
        self.model = model
        self._client = None
        if not self.api_key:
            logger.warning(
                "whowhen: no Jev API key (set %s or pass JevClassifier(api_key=...)); the classifier is "
                "off and only the regex gate is active. Pass use_classifier=False to silence this.",
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

    def probability(self, query: str) -> float | None:
        """Probability that the query needs a filter, or None if the classifier is off or failed."""
        if not self.enabled:
            return None
        try:
            from typesafe_sdk import Choice

            kwargs = {"model": self.model} if self.model else {}
            response = self._get_client().system_one(
                state=f"A user's search query to a document knowledge base: {query}",
                questions={"intent": Choice(instructions=self.QUESTION, criteria=self.CRITERIA)},
                **kwargs,
            )
            return float(response.answers["intent"].probabilities.get("filter", 0.0))
        except Exception:
            logger.warning("whowhen: Jev classifier call failed; treating the query as needing no filter",
                           exc_info=True)
            return None

    def __call__(self, query: str) -> bool:
        p = self.probability(query)
        return p is not None and p > self.threshold
