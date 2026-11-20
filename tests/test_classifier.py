import logging
import sys
import types

from whowhen import JevClassifier


def test_no_key_warns_and_answers_no(monkeypatch, caplog):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with caplog.at_level(logging.WARNING, logger="whowhen"):
        clf = JevClassifier()
    assert not clf.enabled
    assert "no Jev API key" in caplog.text
    assert clf("anything Priya put together?") is False


def _fake_sdk(monkeypatch, prob=None, error=None):
    class Answer:
        probabilities = {"filter": prob, "plain": 1 - prob} if prob is not None else {}

    class Client:
        def __init__(self, api_key):
            self.api_key = api_key

        def system_one(self, state, questions, **kw):
            if error:
                raise error
            return types.SimpleNamespace(answers={"intent": Answer()})

    mod = types.SimpleNamespace(TypeSafeClient=Client, Choice=lambda **kw: kw)
    monkeypatch.setitem(sys.modules, "typesafe_sdk", mod)


def test_threshold(monkeypatch):
    _fake_sdk(monkeypatch, prob=0.8)
    assert JevClassifier(api_key="k")("q") is True
    assert JevClassifier(api_key="k", threshold=0.9)("q") is False


def test_api_error_answers_no(monkeypatch, caplog):
    _fake_sdk(monkeypatch, error=RuntimeError("503"))
    with caplog.at_level(logging.WARNING, logger="whowhen"):
        assert JevClassifier(api_key="k")("q") is False
    assert "failed" in caplog.text
