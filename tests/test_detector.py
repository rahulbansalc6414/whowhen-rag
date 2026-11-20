import logging

import pytest
from conftest import FIELDS, TODAY, FakeClassifier, answer

from whowhen import Condition, Detector, Field, Sort


def test_plain_query_never_calls_llm(make_detector):
    d, llm = make_detector(answer())
    f = d.detect("what is our refund policy?")
    assert not f.needs_filter and not f
    assert f.cleaned_query == "what is our refund policy?"
    assert f.trace.gate == "none" and f.trace.classifier_called and not f.trace.llm_called
    assert llm.prompts == []


def test_regex_hit_skips_classifier(make_detector):
    clf = FakeClassifier(False)
    d, _ = make_detector(answer(), classifier=clf)
    d.detect("pages updated yesterday")
    assert clf.calls == []


def test_time_range_maps_to_your_column(make_detector):
    d, llm = make_detector(answer(
        time_ranges=[{"field": "updated_at", "start": "2026-11-09", "end": "2026-11-16"}],
        cleaned_query="refund policy",
    ))
    f = d.detect("what changed in the refund policy last week?")
    assert f.conditions == [
        Condition("modified_on", ">=", "2026-11-09"),
        Condition("modified_on", "<", "2026-11-16"),
    ]
    assert f.cleaned_query == "refund policy"
    assert f.trace.gate == "regex" and f.trace.llm_called
    prompt = llm.prompts[0]
    assert "2026-11-18 (Wednesday)" in prompt
    assert "modified_on" not in prompt  # the LLM sees roles, not columns
    assert "- updated_at:" in prompt


def test_open_ended_range(make_detector):
    d, _ = make_detector(answer(time_ranges=[{"field": "created_at", "start": "2026-11-01", "end": None}]))
    f = d.detect("specs created this month")
    assert f.conditions == [Condition("created_on", ">=", "2026-11-01")]


def test_person_with_resolver(make_detector):
    directory = {"priya": "priya@example.com"}
    fields = [Field("owner_email", role="created_by", resolve=lambda n: directory.get(n.lower()))]
    d, _ = make_detector(answer(people=[{"field": "created_by", "name": "Priya"}], cleaned_query="caching"),
                         fields=fields)
    f = d.detect("pages written by Priya about caching")
    assert f.conditions == [Condition("owner_email", "=", "priya@example.com")]


def test_unresolved_person_is_dropped_and_reported(make_detector):
    fields = [Field("owner_email", role="created_by", resolve=lambda n: None)]
    d, _ = make_detector(answer(people=[{"field": "created_by", "name": "Zed"}], cleaned_query="caching"),
                         fields=fields)
    f = d.detect("pages written by Zed about caching")
    assert not f.needs_filter
    assert f.trace.unresolved_people == ["Zed"]
    assert f.cleaned_query == "pages written by Zed about caching"


def test_resolver_returning_many_ids_gives_in(make_detector):
    fields = [Field("owner_id", role="created_by", resolve=lambda n: ["u1", "u2"])]
    d, _ = make_detector(answer(people=[{"field": "created_by", "name": "Alex"}]), fields=fields)
    f = d.detect("docs created by Alex")
    assert f.conditions == [Condition("owner_id", "in", ["u1", "u2"])]


def test_two_people_same_role_gives_in(make_detector):
    d, _ = make_detector(answer(people=[{"field": "created_by", "name": "Priya"},
                                        {"field": "created_by", "name": "Marco"}]))
    f = d.detect("pages written by Priya or Marco")
    assert f.conditions == [Condition("owner_email", "in", ["Priya", "Marco"])]


def test_combined_time_and_person(make_detector):
    d, _ = make_detector(answer(
        time_ranges=[{"field": "updated_at", "start": "2026-11-09", "end": "2026-11-16"}],
        people=[{"field": "updated_by", "name": "Priya"}],
        cleaned_query="pricing docs",
    ))
    f = d.detect("pricing docs Priya edited last week")
    assert Condition("last_editor", "=", "Priya") in f.conditions
    assert len(f.conditions) == 3


def test_sort_newest(make_detector):
    d, _ = make_detector(answer(sort={"field": "updated_at", "order": "newest"}, cleaned_query="runbook"))
    f = d.detect("latest deployment runbook")
    assert f.sort == Sort("modified_on", descending=True)
    assert f.needs_filter and f.conditions == []


def test_list_only_clears_query(make_detector):
    d, _ = make_detector(answer(
        time_ranges=[{"field": "created_at", "start": "2026-11-16", "end": None}],
        people=[{"field": "created_by", "name": "Priya"}],
        list_only=True,
    ))
    f = d.detect("pages Priya created this week")
    assert f.list_only and f.cleaned_query == ""


def test_undeclared_role_falls_back_to_only_field_of_that_kind(make_detector):
    fields = [Field("ts", role="created_at")]
    d, _ = make_detector(answer(time_ranges=[{"field": "updated_at", "start": "2026-11-17", "end": "2026-11-18"}]),
                         fields=fields)
    f = d.detect("docs changed yesterday")
    assert f.conditions[0].column == "ts"


def test_prompt_lists_only_declared_roles(make_detector):
    d, llm = make_detector(answer(), fields=[Field("ts", role="created_at")])
    d.detect("docs created yesterday")
    assert "- created_at:" in llm.prompts[0] and "- updated_by:" not in llm.prompts[0]


@pytest.mark.parametrize("bad", ["not json", "```json\n[1, 2]\n```", ""])
def test_unparseable_answer_gives_no_filter(make_detector, bad, caplog):
    d, _ = make_detector(bad)
    with caplog.at_level(logging.WARNING, logger="whowhen"):
        f = d.detect("pages updated yesterday")
    assert not f.needs_filter and f.trace.error
    assert f.cleaned_query == "pages updated yesterday"


def test_fenced_json_is_accepted(make_detector):
    raw = '```json\n{"time_ranges": [{"field": "updated_at", "start": "2026-11-17", "end": "2026-11-18"}]}\n```'
    d, _ = make_detector(raw)
    assert d.detect("pages updated yesterday").needs_filter


def test_invalid_dates_and_unknown_roles_dropped(make_detector):
    d, _ = make_detector(answer(
        time_ranges=[
            {"field": "updated_at", "start": "last tuesday", "end": None},
            {"field": "updated_at", "start": "2026-11-10", "end": "2026-11-01"},
            {"field": "deadline", "start": "2026-11-01", "end": None},
        ],
        people=[{"field": "created_by", "name": "  "}],
    ))
    assert not d.detect("pages updated yesterday").needs_filter


def test_llm_exception_gives_no_filter():
    def broken(prompt):
        raise TimeoutError("model timed out")

    d = Detector(FIELDS, broken, use_classifier=False, today=lambda: TODAY)
    f = d.detect("pages updated yesterday")
    assert not f.needs_filter and "TimeoutError" in f.trace.error


def test_classifier_yes_calls_llm(make_detector):
    d, llm = make_detector(answer(people=[{"field": "created_by", "name": "Priya"}]),
                           classifier=FakeClassifier(True))
    f = d.detect("anything Priya put together on onboarding?")
    assert f.trace.gate == "classifier" and len(llm.prompts) == 1
    assert f.conditions == [Condition("owner_email", "=", "Priya")]


def test_use_classifier_false_means_regex_only(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    d = Detector(FIELDS, lambda p: "{}", use_classifier=False)
    assert d.classifier is None
    t = d.gate("anything Priya put together on onboarding?")
    assert t.gate == "none" and not t.classifier_called


def test_value_formats():
    d = Detector(
        [Field("ts", role="updated_at", value_format="epoch")],
        lambda p: '{"time_ranges": [{"field": "updated_at", "start": "2026-11-17", "end": "2026-11-18"}]}',
        use_classifier=False,
    )
    f = d.detect("docs updated yesterday")
    assert f.conditions == [Condition("ts", ">=", 1794873600), Condition("ts", "<", 1794960000)]


def test_config_errors():
    with pytest.raises(ValueError):
        Detector([], lambda p: "")
    with pytest.raises(ValueError):
        Detector([Field("a", role="created_at"), Field("b", role="created_at")], lambda p: "",
                 use_classifier=False)
    with pytest.raises(ValueError):
        Field("a", role="deadline")
    with pytest.raises(ValueError):
        Field("a", role="created_at", resolve=lambda n: n)
    with pytest.raises(TypeError):
        Detector([Field("a", role="created_at")], "not callable", use_classifier=False)


def test_empty_query(make_detector):
    d, llm = make_detector(answer())
    f = d.detect("   ")
    assert not f.needs_filter and llm.prompts == []
