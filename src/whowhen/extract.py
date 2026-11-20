"""Extraction: the prompt sent to your LLM and the parsing of its answer.

The prompt names roles, never your columns. The answer is validated
strictly: unknown roles, bad dates and empty names are dropped rather than
guessed at.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date

from .fields import DEFAULT_DESCRIPTIONS, PERSON_ROLES, TIME_ROLES, Field

PROMPT_TEMPLATE = """You turn a search query into metadata filters for a document search.
Today is {today} ({weekday}).

Filters you may use:
{filters}

Answer with JSON only, using exactly these keys:
{{
  "time_ranges": [{{"field": "<time filter>", "start": "YYYY-MM-DD or null", "end": "YYYY-MM-DD or null"}}],
  "people": [{{"field": "<person filter>", "name": "<name as written in the query>"}}],
  "sort": {{"field": "<time filter>", "order": "newest or oldest"}} or null,
  "list_only": true or false,
  "cleaned_query": "<the query without its time and person conditions>"
}}

Rules:
- Use only the filter names listed above. Leave a list empty when the query has no such condition.
- start is inclusive and end is exclusive; null means open-ended. Weeks start on Monday.
  Examples: "yesterday" = yesterday to today. "last week" = the previous Monday to this Monday.
  "this month" = the 1st of this month to null. "last 30 days" = today minus 30 days to null.
  "in 2025" = 2025-01-01 to 2026-01-01.
- "recent", "latest", "newest" with no period: no time range, sort by newest.
- A person filter is someone who wrote, created, edited or owns documents. Copy the name as written.
  A person who is only the topic of the question is not a filter ("what is Priya's role?" has none).
- list_only is true when the query only asks to list or count documents and names no topic to
  search for ("pages Priya created this week"). cleaned_query is then "".
- cleaned_query keeps the topic words, e.g. "pricing docs Priya updated last week" -> "pricing docs".
- If the query has no time or person condition: empty lists, sort null, list_only false,
  cleaned_query = the query unchanged.

Query: {query}"""


def build_prompt(query: str, fields: list[Field], today: date) -> str:
    seen: dict[str, str] = {}
    for f in fields:
        seen.setdefault(f.role, f.description or DEFAULT_DESCRIPTIONS[f.role])
    lines = [f"- {role}: {desc}" for role, desc in seen.items()]
    return PROMPT_TEMPLATE.format(
        today=today.isoformat(), weekday=today.strftime("%A"), filters="\n".join(lines), query=query
    )


@dataclass
class Extraction:
    """The LLM's answer after validation, still in terms of roles."""

    time_ranges: list[tuple[str, date | None, date | None]] = field(default_factory=list)
    people: list[tuple[str, str]] = field(default_factory=list)
    sort: tuple[str, str] | None = None  # (role, "newest" | "oldest")
    list_only: bool = False
    cleaned_query: str = ""


class ExtractionError(ValueError):
    """The LLM's answer was not usable JSON."""


def _load_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ExtractionError(f"No JSON object in LLM answer: {text[:200]!r}")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise ExtractionError(f"Invalid JSON in LLM answer: {e}") from e
    if not isinstance(data, dict):
        raise ExtractionError("LLM answer is not a JSON object")
    return data


def _parse_date(value) -> date | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _pick_role(role, declared: set[str], kind: tuple[str, ...]) -> str | None:
    """Use the role if declared; else fall back to the only declared role of the same kind."""
    if role in declared:
        return role
    same_kind = [r for r in kind if r in declared]
    return same_kind[0] if len(same_kind) == 1 else None


def parse_answer(text: str, fields: list[Field]) -> Extraction:
    data = _load_json(text)
    declared = {f.role for f in fields}
    out = Extraction()

    for item in data.get("time_ranges") or []:
        if not isinstance(item, dict):
            continue
        role = _pick_role(item.get("field"), declared, TIME_ROLES)
        start, end = _parse_date(item.get("start")), _parse_date(item.get("end"))
        if role is None or (start is None and end is None):
            continue
        if start is not None and end is not None and start >= end:
            continue
        out.time_ranges.append((role, start, end))

    for item in data.get("people") or []:
        if not isinstance(item, dict):
            continue
        role = _pick_role(item.get("field"), declared, PERSON_ROLES)
        name = item.get("name")
        if role is None or not isinstance(name, str) or not name.strip():
            continue
        out.people.append((role, name.strip()))

    sort = data.get("sort")
    if isinstance(sort, dict) and sort.get("order") in ("newest", "oldest"):
        role = _pick_role(sort.get("field"), declared, TIME_ROLES)
        if role is not None:
            out.sort = (role, sort["order"])

    out.list_only = bool(data.get("list_only"))
    cleaned = data.get("cleaned_query")
    out.cleaned_query = cleaned.strip() if isinstance(cleaned, str) else ""
    return out
