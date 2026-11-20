import json
from datetime import date

import pytest

from whowhen import Detector, Field

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
    def __init__(self, result: bool):
        self.result = result
        self.calls: list[str] = []

    def __call__(self, query: str) -> bool:
        self.calls.append(query)
        return self.result


def answer(time_ranges=(), people=(), sort=None, list_only=False, cleaned_query=""):
    return {
        "time_ranges": list(time_ranges),
        "people": list(people),
        "sort": sort,
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
