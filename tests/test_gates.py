import pytest
from queries import CLASSIFIER_ONLY, PLAIN, REGEX_AUTHOR, REGEX_TIME

from whowhen_rag import regex_signal


@pytest.mark.parametrize("query", REGEX_TIME)
def test_time_wording_hits(query):
    assert regex_signal(query) == "time"


@pytest.mark.parametrize("query", REGEX_AUTHOR)
def test_author_wording_hits(query):
    assert regex_signal(query) in ("author", "time")


@pytest.mark.parametrize("query", PLAIN)
def test_plain_questions_miss(query):
    assert regex_signal(query) is None


@pytest.mark.parametrize("query", CLASSIFIER_ONLY)
def test_classifier_only_queries_miss_regex(query):
    # Documents the regex's limits: these are what gate 2 exists for.
    assert regex_signal(query) is None
