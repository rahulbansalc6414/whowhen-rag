"""Year check: correct the year the LLM picked for a month named without a year.

LLMs given today's date still sometimes put "since September" in last year. This
module does not parse dates. It only checks one fact in the LLM's answer: when
the query names a month with no year next to it, and a returned range starts
in that month, the year must be the latest one in which that month has begun.
If it is not, the whole range moves by the difference in years.

Only start dates are checked: an end can rightly be in the future ("before
December", asked in November, means up to now).
"""
from __future__ import annotations

import re
from datetime import date

from .extract import Extraction

_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4,
    "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9, "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
_MONTH_RE = re.compile(r"\b(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\b", re.IGNORECASE)
_YEAR_AFTER = re.compile(r"^[\s,]*(?:of\s+)?(?:19|20)\d{2}\b")
_YEAR_BEFORE = re.compile(r"\b(?:19|20)\d{2}[\s,]*$")
# "may" is usually the verb; only count it as a month after a word that introduces a date.
_MAY_CONTEXT = re.compile(
    r"\b(?:in|since|before|after|until|till|from|during|of|by|between|and|to|through|early|late|mid)\s+$",
    re.IGNORECASE,
)


def months_without_year(query: str) -> set[int]:
    """Months named in the query with no year attached ("since September" yes, "September 2025" no)."""
    found: set[int] = set()
    for m in _MONTH_RE.finditer(query):
        word = m.group(1).lower()
        before, after = query[: m.start()], query[m.end() :]
        if word == "may" and not _MAY_CONTEXT.search(before):
            continue
        if _YEAR_AFTER.match(after) or _YEAR_BEFORE.search(before):
            continue
        found.add(_MONTHS[word])
    return found


def latest_started_year(month: int, today: date) -> int:
    """The latest year in which this month has begun, as of today."""
    return today.year if date(today.year, month, 1) <= today else today.year - 1


def _shift(d: date | None, years: int) -> date | None:
    if d is None or years == 0:
        return d
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29 February
        return d.replace(year=d.year + years, day=28)


def fix_month_years(query: str, extraction: Extraction, today: date) -> list[str]:
    """Correct years in place; return a description of each correction made."""
    months = months_without_year(query)
    if not months:
        return []
    corrections: list[str] = []
    fixed = []
    for role, start, end in extraction.time_ranges:
        if start is not None and start.month in months:
            years = latest_started_year(start.month, today) - start.year
            if years:
                new_start, new_end = _shift(start, years), _shift(end, years)
                corrections.append(f"{role}: {start} to {end} -> {new_start} to {new_end}")
                start, end = new_start, new_end
        fixed.append((role, start, end))
    extraction.time_ranges = fixed
    return corrections
