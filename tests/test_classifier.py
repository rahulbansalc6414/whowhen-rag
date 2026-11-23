import logging
import sys
import types

from whowhen_rag import JevClassifier


def test_no_key_warns_and_answers_no(monkeypatch, caplog):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with caplog.at_level(logging.WARNING, logger="whowhen_rag"):
        clf = JevClassifier()
    assert not clf.enabled
    assert "no Jev API key" in caplog.text
    assert clf("anything Priya put together?") is False


def _fake_sdk(monkeypatch, prob=None, error=None, recency_probs=None):
    class Answer:
        def __init__(self, probabilities):
            self.probabilities = probabilities

    class Client:
        def __init__(self, api_key):
            self.api_key = api_key

        def system_one(self, state, questions, **kw):
            if error:
                raise error
            answers = {}
            if "intent" in questions:
                answers["intent"] = Answer({"filter": prob, "plain": 1 - prob} if prob is not None else {})
            if "recency" in questions:
                answers["recency"] = Answer(recency_probs or {"neither": 1.0})
            Client.last_questions = sorted(questions)
            return types.SimpleNamespace(answers=answers)

    mod = types.SimpleNamespace(TypeSafeClient=Client, Choice=lambda **kw: kw)
    monkeypatch.setitem(sys.modules, "typesafe_sdk", mod)
    return Client


def test_default_threshold_is_inclusive_at_0_6(monkeypatch):
    _fake_sdk(monkeypatch, prob=0.6)
    assert JevClassifier(api_key="k").threshold == 0.6
    assert JevClassifier(api_key="k")("q") is True
    _fake_sdk(monkeypatch, prob=0.59)
    assert JevClassifier(api_key="k")("q") is False


def test_threshold(monkeypatch):
    _fake_sdk(monkeypatch, prob=0.8)
    assert JevClassifier(api_key="k")("q") is True
    assert JevClassifier(api_key="k", threshold=0.9)("q") is False


def test_api_error_answers_no(monkeypatch, caplog):
    _fake_sdk(monkeypatch, error=RuntimeError("503"))
    with caplog.at_level(logging.WARNING, logger="whowhen_rag"):
        assert JevClassifier(api_key="k")("q") is False
    assert "failed" in caplog.text


def test_judge_asks_both_questions_in_one_call(monkeypatch):
    client = _fake_sdk(monkeypatch, prob=0.9, recency_probs={"newest": 0.97, "oldest": 0.0, "neither": 0.03})
    j = JevClassifier(api_key="k").judge("fresh material on search")
    assert client.last_questions == ["intent", "recency"]
    assert j.filter_p == 0.9 and j.recency == "newest" and j.recency_p == 0.97


def test_recency_below_threshold_is_none(monkeypatch):
    _fake_sdk(monkeypatch, prob=0.9, recency_probs={"newest": 0.9, "oldest": 0.0, "neither": 0.1})
    assert JevClassifier(api_key="k").judge("q").recency is None
    assert JevClassifier(api_key="k", recency_threshold=0.85).judge("q").recency == "newest"


def test_recency_only_question(monkeypatch):
    client = _fake_sdk(monkeypatch, recency_probs={"newest": 0.0, "oldest": 0.99, "neither": 0.01})
    j = JevClassifier(api_key="k").judge("q", ask_filter=False)
    assert client.last_questions == ["recency"] and j.filter_p is None and j.recency == "oldest"
