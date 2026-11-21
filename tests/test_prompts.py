from datetime import date

import pytest
from conftest import FIELDS, TODAY, FakeLLM, answer

from whowhen import Detector
from whowhen.extract import BUILTIN_PROMPTS, build_prompt, load_prompt


@pytest.mark.parametrize("name", BUILTIN_PROMPTS)
def test_builtin_prompts_load_and_fill(name):
    text = build_prompt("pages written by Priya", FIELDS, date(2026, 11, 18), load_prompt(name))
    assert "Query: pages written by Priya" in text
    assert "Today is 2026-11-18 (Wednesday)." in text
    assert "- created_at:" in text and "{filters}" not in text
    assert '"time_ranges": [{"field"' in text  # literal JSON braces survive


def test_default_is_v2():
    assert load_prompt() == load_prompt("v2")
    assert "calendar month" in load_prompt("v2") and "calendar month" not in load_prompt("v1")


def test_query_text_is_never_treated_as_placeholder():
    text = build_prompt("notes about {filters} and {today}", FIELDS, TODAY, load_prompt("v2"))
    assert text.endswith("Query: notes about {filters} and {today}")


def test_custom_template_text_and_file(tmp_path):
    custom = "Date {today}. Roles:\n{filters}\nReturn JSON for: {query}"
    llm = FakeLLM(answer())
    Detector(FIELDS, llm, use_classifier=False, today=lambda: TODAY, prompt=custom).detect("docs updated yesterday")
    assert llm.prompts[0].startswith("Date 2026-11-18. Roles:\n- created_at:")

    path = tmp_path / "mine.txt"
    path.write_text(custom + "\n")
    assert load_prompt(str(path)) == custom


def test_bad_prompts_fail_at_construction(tmp_path):
    with pytest.raises(ValueError, match="missing placeholders"):
        Detector(FIELDS, lambda p: "", use_classifier=False, prompt="Only {query}")
    with pytest.raises(ValueError, match="not a built-in"):
        Detector(FIELDS, lambda p: "", use_classifier=False, prompt="v9")
