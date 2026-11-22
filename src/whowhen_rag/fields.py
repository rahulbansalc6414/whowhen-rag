"""Fields: how your metadata columns map to the roles whowhen understands.

The LLM never sees your column names. It answers in terms of roles
("created_at", "updated_by", ...) and whowhen maps each role to the column
you declared for it, formatting values the way your store expects.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Literal

Role = Literal["created_at", "updated_at", "created_by", "updated_by"]
ValueFormat = Literal["date", "datetime", "epoch", "epoch_ms"]

#: Roles that hold a point in time.
TIME_ROLES: tuple[str, ...] = ("created_at", "updated_at")
#: Roles that hold a person.
PERSON_ROLES: tuple[str, ...] = ("created_by", "updated_by")

DEFAULT_DESCRIPTIONS: dict[str, str] = {
    "created_at": "when the document was created",
    "updated_at": "when the document was last edited",
    "created_by": "who created or wrote the document",
    "updated_by": "who last edited the document",
}

#: Maps a person's name as written in the query to the value stored in your
#: column (an ID, an email, a list of IDs), or None if the name is unknown.
Resolver = Callable[[str], str | int | list | None]


@dataclass(frozen=True)
class Field:
    """One filterable column in your store.

    Args:
        column: The column or metadata key name in your store, e.g. "modified_on".
        role: What the column means; one of created_at, updated_at, created_by, updated_by.
        resolve: Person fields only. Turns a name from the query into your stored value.
            Without it, the name is used as written.
        value_format: Time fields only. How dates are written into filters:
            "date" (2026-11-09), "datetime" (2026-11-09T00:00:00+00:00),
            "epoch" (seconds) or "epoch_ms" (milliseconds).
        description: Optional override for the description the LLM sees for this role.
    """

    column: str
    role: Role
    resolve: Resolver | None = None
    value_format: ValueFormat = "date"
    description: str | None = None

    def __post_init__(self) -> None:
        if self.role not in TIME_ROLES + PERSON_ROLES:
            raise ValueError(f"Unknown role {self.role!r}; use one of {TIME_ROLES + PERSON_ROLES}")
        if not self.column:
            raise ValueError("Field.column must not be empty")
        if self.resolve is not None and self.role not in PERSON_ROLES:
            raise ValueError(f"resolve= only applies to person roles, not {self.role!r}")

    @property
    def is_time(self) -> bool:
        return self.role in TIME_ROLES

    def format_date(self, d: date) -> str | int:
        """Write a date the way this field's store expects it (midnight UTC for timestamps)."""
        if self.value_format == "date":
            return d.isoformat()
        dt = datetime.combine(d, time.min, tzinfo=timezone.utc)
        if self.value_format == "datetime":
            return dt.isoformat()
        if self.value_format == "epoch":
            return int(dt.timestamp())
        return int(dt.timestamp() * 1000)
