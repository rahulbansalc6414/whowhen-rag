import json
import socket
from datetime import date

import pytest

from whowhen_rag import Detector, Field

TODAY = date(2026, 11, 18)  # a Wednesday


class FakeLLM:
    """Returns a canned answer and records the prompts it was given."""

    def __init__(self, answer):
        self.answer = answer if isinstance(answer, str) else json.dumps(answer)
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.answer


class FakeClassifier:
    """A plain function-style classifier (query -> bool): filter gate only, no recency."""

    def __init__(self, result: bool):
        self.result = result
        self.calls: list[str] = []

    def __call__(self, query: str) -> bool:
        self.calls.append(query)
        return self.result


class FakeJev:
    """Stands in for JevClassifier: answers the filter and recency questions."""

    threshold = 0.6

    def __init__(self, filter_p: float = 0.0, recency: str | None = None, recency_p: float = 0.0):
        self.filter_p, self.recency, self.recency_p = filter_p, recency, recency_p
        self.calls: list[tuple[str, bool, bool]] = []

    def judge(self, query, *, ask_filter=True, ask_recency=True):
        from whowhen_rag import Judgement
        self.calls.append((query, ask_filter, ask_recency))
        return Judgement(filter_p=self.filter_p if ask_filter else None,
                         recency=self.recency if ask_recency else None,
                         recency_p=self.recency_p if ask_recency else None)


def answer(time_ranges=(), people=(), list_only=False, cleaned_query=""):
    return {
        "time_ranges": list(time_ranges),
        "people": list(people),
        "list_only": list_only,
        "cleaned_query": cleaned_query,
    }


FIELDS = [
    Field("created_on", role="created_at"),
    Field("modified_on", role="updated_at"),
    Field("owner_email", role="created_by"),
    Field("last_editor", role="updated_by"),
]


@pytest.fixture
def make_detector():
    def _make(llm_answer, fields=FIELDS, classifier=None, **kw):
        llm = FakeLLM(llm_answer)
        d = Detector(fields, llm, classifier=classifier or FakeClassifier(False), today=lambda: TODAY, **kw)
        return d, llm

    return _make


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Every test fails loudly if it tries to open a network connection."""
    def refuse(*args, **kwargs):
        raise RuntimeError("tests must not use the network")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
