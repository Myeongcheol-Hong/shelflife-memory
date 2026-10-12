import json
from datetime import UTC, date, datetime

import pytest

from shelflife.models import CheckMethod, Claim, FieldSource, Kind, Status, Volatility, parse_enum

CLAIM = Claim(
    id="c1",
    text="Use library X",
    kind=Kind.DECISION,
    subject=None,
    attribute=None,
    value=None,
    volatility=Volatility.NONE,
    volatility_source=FieldSource.DEFAULT,
    check_method=CheckMethod.NONE,
    check_method_source=FieldSource.CALLER,
    check_target=None,
    source_url=None,
    source_quote=None,
    observed_at=date(2026, 10, 8),
    recorded_at=datetime(2026, 10, 12, 9, 30, tzinfo=UTC),
    last_checked_at=None,
    next_check_at=None,
    status=Status.FRESH,
    depends_on=("a", "b"),
)


def test_to_dict_is_json_ready_and_from_dict_inverts_it():
    data = CLAIM.to_dict()
    assert json.loads(json.dumps(data)) == data
    assert type(data["kind"]) is str and data["kind"] == "decision"
    assert data["observed_at"] == "2026-10-08"
    assert data["recorded_at"] == "2026-10-12T09:30:00+00:00"
    assert data["depends_on"] == ["a", "b"]
    assert Claim.from_dict(data) == CLAIM


def test_parse_enum_names_the_allowed_values():
    assert parse_enum(Volatility, "slow", "volatility") is Volatility.SLOW
    with pytest.raises(ValueError, match=r"one of: fast, medium, slow, none \(got 'daily'\)"):
        parse_enum(Volatility, "daily", "volatility")
