"""The result of detect(): filters on your columns, ready for your store."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Op = Literal[">=", "<", "=", "in"]


@dataclass(frozen=True)
class Condition:
    column: str
    op: Op
    value: Any


@dataclass(frozen=True)
class Sort:
    column: str
    descending: bool


@dataclass
class Trace:
    """What happened inside detect(), for logging and cost tracking."""

    gate: Literal["regex", "classifier", "none"] = "none"
    classifier_called: bool = False
    llm_called: bool = False
    error: str | None = None
    unresolved_people: list[str] = field(default_factory=list)


@dataclass
class Filters:
    """Filters to apply to a search. All conditions are combined with AND.

    Attributes:
        conditions: Conditions on your columns.
        sort: Order results by this column, or None.
        list_only: The query only asks to list documents; skip semantic search if you can.
        cleaned_query: The query without its time and person words, for the semantic search.
        trace: Which gates ran and whether the LLM was called.
    """

    conditions: list[Condition] = field(default_factory=list)
    sort: Sort | None = None
    list_only: bool = False
    cleaned_query: str = ""
    trace: Trace = field(default_factory=Trace)

    @property
    def needs_filter(self) -> bool:
        return bool(self.conditions or self.sort or self.list_only)

    def __bool__(self) -> bool:
        return self.needs_filter

    def to_dict(self) -> dict:
        return asdict(self)

    # --- SQL -----------------------------------------------------------------

    def to_sql(self, placeholder: str = "%s") -> tuple[str, list]:
        """A parameterised WHERE clause (without the word WHERE) and its parameters.

        Returns ("", []) when there are no conditions. Column names come from
        your Field declarations and are quoted; values are always parameters.
        Use placeholder="?" for sqlite.
        """
        parts: list[str] = []
        params: list = []
        for c in self.conditions:
            col = _quote(c.column)
            if c.op == "in":
                values = list(c.value)
                parts.append(f"{col} IN ({', '.join([placeholder] * len(values))})")
                params.extend(values)
            else:
                parts.append(f"{col} {c.op} {placeholder}")
                params.append(c.value)
        return " AND ".join(parts), params

    def order_by_sql(self) -> str:
        """An ORDER BY clause (with the words ORDER BY), or "" when there is no sort."""
        if self.sort is None:
            return ""
        return f"ORDER BY {_quote(self.sort.column)} {'DESC' if self.sort.descending else 'ASC'}"

    # --- Vector stores -------------------------------------------------------

    def to_chroma(self) -> dict | None:
        """A Chroma ``where`` filter, or None when there are no conditions.

        Chroma compares ranges on numbers only: declare time fields with
        value_format="epoch" when your dates are stored as timestamps.
        """
        ops = {">=": "$gte", "<": "$lt", "=": "$eq", "in": "$in"}
        clauses = [{c.column: {ops[c.op]: list(c.value) if c.op == "in" else c.value}} for c in self.conditions]
        if not clauses:
            return None
        return clauses[0] if len(clauses) == 1 else {"$and": clauses}

    def to_qdrant(self) -> dict | None:
        """A Qdrant filter as a dict (``{"must": [...]}``), or None when there are no conditions.

        Pass it as ``query_filter=models.Filter(**filters.to_qdrant())`` or in a REST body.
        """
        ranges: dict[str, dict] = {}
        must: list[dict] = []
        for c in self.conditions:
            if c.op in (">=", "<"):
                ranges.setdefault(c.column, {})["gte" if c.op == ">=" else "lt"] = c.value
            elif c.op == "in":
                must.append({"key": c.column, "match": {"any": list(c.value)}})
            else:
                must.append({"key": c.column, "match": {"value": c.value}})
        must = [{"key": col, "range": r} for col, r in ranges.items()] + must
        return {"must": must} if must else None


def _quote(column: str) -> str:
    return ".".join('"' + part.replace('"', '""') + '"' for part in column.split("."))
