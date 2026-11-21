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
from importlib.resources import files
from pathlib import Path

from .fields import DEFAULT_DESCRIPTIONS, PERSON_ROLES, TIME_ROLES, Field

PROMPTS_DIR = files("whowhen") / "prompts"
BUILTIN_PROMPTS: tuple[str, ...] = ("v1", "v2")
DEFAULT_PROMPT = "v2"
REQUIRED_PLACEHOLDERS: tuple[str, ...] = ("{query}", "{filters}", "{today}")


def load_prompt(prompt: str = DEFAULT_PROMPT) -> str:
    """Return a prompt template from a built-in name ("v1", "v2"), a file path, or template text.

    Templates use {query}, {filters}, {today} (required) and {weekday} (optional).
    Every other brace is literal, so JSON examples need no escaping.
    """
    if prompt in BUILTIN_PROMPTS:
        template = (PROMPTS_DIR / f"{prompt}.txt").read_text(encoding="utf-8").rstrip("\n")
    elif "{query}" in prompt:
        template = prompt
    else:
        path = Path(prompt).expanduser()
        if not path.is_file():
            raise ValueError(
                f"prompt={prompt!r} is not a built-in prompt {BUILTIN_PROMPTS}, a file, or a template "
                "containing {query}"
            )
        template = path.read_text(encoding="utf-8").rstrip("\n")
    missing = [p for p in REQUIRED_PLACEHOLDERS if p not in template]
    if missing:
        raise ValueError(f"Prompt template is missing placeholders: {', '.join(missing)}")
    return template


def build_prompt(query: str, fields: list[Field], today: date, template: str | None = None) -> str:
    seen: dict[str, str] = {}
    for f in fields:
        seen.setdefault(f.role, f.description or DEFAULT_DESCRIPTIONS[f.role])
    lines = [f"- {role}: {desc}" for role, desc in seen.items()]
    text = template if template is not None else load_prompt()
    # The query goes in last so text inside it is never treated as a placeholder.
    for key, value in (("{today}", today.isoformat()), ("{weekday}", today.strftime("%A")),
                       ("{filters}", "\n".join(lines))):
        text = text.replace(key, value)
    return text.replace("{query}", query)


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
