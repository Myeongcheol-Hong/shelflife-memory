"""Claim model and its enums (design 4.1 and 4.2)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields
from datetime import date, datetime
from enum import StrEnum
from typing import Any, TypeVar


class Kind(StrEnum):
    WORLD_FACT = "world_fact"
    DECISION = "decision"
    PREFERENCE = "preference"
    NOTE = "note"


class Volatility(StrEnum):
    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"
    NONE = "none"


class CheckMethod(StrEnum):
    PYPI = "pypi"
    GITHUB_RELEASE = "github_release"
    WEB_PAGE = "web_page"
    NONE = "none"


class Status(StrEnum):
    FRESH = "fresh"
    DUE = "due"
    CHANGED = "changed"
    UNVERIFIABLE = "unverifiable"
    RETIRED = "retired"


class FieldSource(StrEnum):
    """Who set a claim's volatility or check_method.

    M2 rules may replace a DEFAULT value but never a CALLER value. The write eval
    (design 6.0) uses this to tell the two apart. Under D4, Claude sets volatility only at
    write time through remember, which records CALLER; there is no LLM source.
    """

    CALLER = "caller"
    DEFAULT = "default"
    RULE = "rule"


# Volatility used when the caller gives none. World facts default to fast because
# labeling fast as slow is the expensive error (design 6.0): checks come too late.
DEFAULT_VOLATILITY: dict[Kind, Volatility] = {
    Kind.WORLD_FACT: Volatility.FAST,
    Kind.DECISION: Volatility.NONE,
    Kind.PREFERENCE: Volatility.NONE,
    Kind.NOTE: Volatility.NONE,
}


E = TypeVar("E", bound=StrEnum)


def parse_enum(enum_cls: type[E], value: str, field_name: str) -> E:
    """Convert a string to an enum member, with an error that lists the allowed values."""
    try:
        return enum_cls(value)
    except ValueError:
        allowed = ", ".join(member.value for member in enum_cls)
        raise ValueError(f"{field_name} must be one of: {allowed} (got {value!r})") from None


@dataclass(frozen=True)
class Claim:
    id: str
    text: str
    kind: Kind
    subject: str | None
    attribute: str | None
    value: str | None
    volatility: Volatility
    volatility_source: FieldSource
    check_method: CheckMethod
    check_method_source: FieldSource
    check_target: str | None
    source_url: str | None
    source_quote: str | None
    observed_at: date
    recorded_at: datetime
    last_checked_at: datetime | None
    next_check_at: date | None
    status: Status
    depends_on: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Claim:
        """Inverse of to_dict. Every field must be present."""
        values = {}
        for f in fields(cls):
            v = data[f.name]
            convert = _FROM_STR.get(f.name)
            values[f.name] = convert(v) if convert and v is not None else v
        return cls(**values)

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready dict: enums as strings, dates and times in ISO 8601."""
        out: dict[str, Any] = {}
        for f in fields(self):
            v = getattr(self, f.name)
            if isinstance(v, StrEnum):
                v = v.value
            elif isinstance(v, date):  # also covers datetime
                v = v.isoformat()
            elif isinstance(v, tuple):
                v = list(v)
            out[f.name] = v
        return out


_FROM_STR: dict[str, Callable[[Any], Any]] = {
    "kind": Kind,
    "volatility": Volatility,
    "volatility_source": FieldSource,
    "check_method": CheckMethod,
    "check_method_source": FieldSource,
    "status": Status,
    "observed_at": date.fromisoformat,
    "next_check_at": date.fromisoformat,
    "recorded_at": datetime.fromisoformat,
    "last_checked_at": datetime.fromisoformat,
    "depends_on": tuple,
}
