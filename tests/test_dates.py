from datetime import date

import pytest
from conftest import FIELDS, TODAY, answer

from whowhen_rag import Condition, Detector
from whowhen_rag.dates import fix_month_years, latest_started_year, months_without_year
from whowhen_rag.extract import Extraction

D = date.fromisoformat


@pytest.mark.parametrize("query, months", [
    ("what changed since September", {9}),
    ("docs modified in October", {10}),
    ("pages created between June and August", {6, 8}),
    ("notes from Sept", {9}),
    ("what was written in March 2025", set()),
    ("the 2025 March offsite", set()),
    ("pages that may be outdated", set()),      # "may" the verb
    ("design docs created in May", {5}),
    ("no month here", set()),
])
def test_months_without_year(query, months):
    assert months_without_year(query) == months


def test_latest_started_year():
    assert latest_started_year(9, TODAY) == 2026    # Sept 2026 has begun (today 2026-11-18)
    assert latest_started_year(12, TODAY) == 2025   # Dec 2026 has not
    assert latest_started_year(11, TODAY) == 2026   # this month counts


def test_since_september_moved_to_this_year():
    ex = Extraction(time_ranges=[("updated_at", D("2025-09-01"), None)])
    fixes = fix_month_years("what changed in the vendor policy since September", ex, TODAY)
    assert ex.time_ranges == [("updated_at", D("2026-09-01"), None)]
    assert fixes == ["updated_at: 2025-09-01 to None -> 2026-09-01 to None"]


def test_whole_range_moves():
    ex = Extraction(time_ranges=[("updated_at", D("2025-10-01"), D("2025-11-01"))])
    fix_month_years("docs modified in October", ex, TODAY)
    assert ex.time_ranges == [("updated_at", D("2026-10-01"), D("2026-11-01"))]


def test_future_month_goes_back_a_year():
    ex = Extraction(time_ranges=[("updated_at", D("2026-12-01"), None)])
    fix_month_years("design docs updated since December", ex, TODAY)
    assert ex.time_ranges == [("updated_at", D("2025-12-01"), None)]


@pytest.mark.parametrize("query, start, end", [
    ("docs modified in October", "2026-10-01", "2026-11-01"),        # already right
    ("what was written in March 2025", "2025-03-01", "2025-04-01"),  # year given
    ("pages updated last week", "2026-11-09", "2026-11-16"),         # no month named
])
def test_left_alone(query, start, end):
    ex = Extraction(time_ranges=[("updated_at", D(start), D(end))])
    assert fix_month_years(query, ex, TODAY) == []
    assert ex.time_ranges == [("updated_at", D(start), D(end))]


def test_end_only_ranges_are_not_touched():
    # "before December" asked in November means up to now; its end may be in the future.
    ex = Extraction(time_ranges=[("created_at", None, D("2026-12-01"))])
    assert fix_month_years("pages created before December", ex, TODAY) == []


def test_detector_applies_fix_and_records_it(make_detector):
    d, _ = make_detector(answer(time_ranges=[{"field": "updated_at", "start": "2025-09-01", "end": None}]),
                         fix_years=True)
    f = d.detect("what changed in the vendor policy since September")
    assert f.conditions == [Condition("modified_on", ">=", "2026-09-01")]
    assert f.trace.year_corrections


def test_fix_years_false_keeps_llm_answer():
    llm = lambda p: '{"time_ranges": [{"field": "updated_at", "start": "2025-09-01", "end": null}]}'
    d = Detector(FIELDS, llm, use_classifier=False, today=lambda: TODAY)  # off by default
    f = d.detect("what changed in the vendor policy since September")
    assert f.conditions == [Condition("modified_on", ">=", "2025-09-01")]
    assert f.trace.year_corrections == []
