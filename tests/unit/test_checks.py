"""Recording checks (D9)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from shelflife.models import CheckMethod, CheckResult, Status

PYPI = {"check_method": "pypi", "check_target": "mcp", "volatility": "fast"}


@pytest.fixture
def claim(store):
    # observed 2026-10-01, so due since 2026-10-08; the clock says 2026-10-12.
    return store.remember(
        "The latest mcp is 2.3.0", "world_fact", value="2.3.0", observed_at="2026-10-01", **PYPI
    )


def checks(store, claim_id):
    rows = store._conn.execute(
        "SELECT * FROM checks WHERE claim_id = ? ORDER BY rowid", (claim_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def test_same_makes_the_claim_fresh_until_one_interval_after_the_check(store, claim):
    updated, check = store.add_check(claim.id, CheckResult.SAME, "2.3.0", "2.3.0")

    assert updated.status is Status.FRESH
    assert updated.last_checked_at == datetime(2026, 10, 12, 9, 30, tzinfo=UTC)
    assert updated.next_check_at == date(2026, 10, 19)
    assert updated.observed_at == claim.observed_at  # the user's observation stays
    assert (check.method, check.old_value, check.new_value) == (CheckMethod.PYPI, "2.3.0", "2.3.0")
    assert check.to_dict() == {
        "result": "same",
        "old_value": "2.3.0",
        "new_value": "2.3.0",
        "evidence": "2.3.0",
        "checked_at": "2026-10-12T09:30:00+00:00",
    }
    assert [r["id"] for r in checks(store, claim.id)] == [check.id]
    assert store.due() == []


def test_changed_keeps_the_value_and_logs_old_and_new(store, claim):
    updated, _ = store.add_check(claim.id, CheckResult.CHANGED, "2.4.0", "2.4.0")

    assert (updated.status, updated.value) == (Status.CHANGED, "2.3.0")
    assert updated.next_check_at == date(2026, 10, 19)
    [row] = checks(store, claim.id)
    assert (row["result"], row["old_value"], row["new_value"]) == ("changed", "2.3.0", "2.4.0")
    assert (row["method"], row["cost_usd"]) == ("pypi", None)


@pytest.mark.parametrize("result", [CheckResult.ERROR, CheckResult.CANNOT_TELL])
def test_inconclusive_checks_keep_the_claim_due_until_the_third_in_a_row(
    store, claim, clock, result
):
    for _ in range(2):
        updated, _ = store.add_check(claim.id, result, evidence="HTTP 503")
        assert (updated.status, updated.next_check_at) == (Status.FRESH, date(2026, 10, 8))
        assert [c.id for c in store.due()] == [claim.id]
        clock.now += timedelta(days=1)

    updated, _ = store.add_check(claim.id, result, evidence="HTTP 503")  # third: 10-14
    assert updated.next_check_at == date(2026, 10, 21)
    assert store.due() == []
    assert updated.last_checked_at == datetime(2026, 10, 14, 9, 30, tzinfo=UTC)


def test_a_conclusive_check_resets_the_count(store, claim):
    store.add_check(claim.id, CheckResult.ERROR)
    store.add_check(claim.id, CheckResult.ERROR)
    store.add_check(claim.id, CheckResult.SAME, "2.3.0", "2.3.0")  # next: 10-19
    updated, _ = store.add_check(claim.id, CheckResult.ERROR)
    assert updated.next_check_at == date(2026, 10, 19)  # one error: the date stays


def test_an_inconclusive_check_leaves_a_changed_claim_changed(store, claim):
    store.add_check(claim.id, CheckResult.CHANGED, "2.4.0", "2.4.0")
    updated, _ = store.add_check(claim.id, CheckResult.ERROR, evidence="timeout")
    assert updated.status is Status.CHANGED


def test_checks_are_refused_for_claims_that_cannot_be_checked(store, claim):
    unverifiable = store.remember("Seoul has 25 districts", "world_fact")
    note = store.remember("A note", "note")
    with store._conn:  # forget arrives in M2c
        store._conn.execute("UPDATE claims SET status = 'retired' WHERE id = ?", (claim.id,))
    for claim_id, message in [
        ("nope", "no claim with id 'nope'"),
        (claim.id, "is retired"),
        (unverifiable.id, "has no check_method"),
        (note.id, "has no check_method"),
    ]:
        with pytest.raises(ValueError, match=message):
            store.add_check(claim_id, CheckResult.SAME)
        with pytest.raises(ValueError, match=message):
            store.checkable(claim_id)
    assert store._conn.execute("SELECT count(*) FROM checks").fetchone()[0] == 0
