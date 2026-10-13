"""Recording checks (D9)."""

from datetime import UTC, date, datetime, timedelta, timezone

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

    # Past the limit, each further one moves the next check out again.
    clock.now += timedelta(days=7)  # 10-21
    for expected in (date(2026, 10, 28), date(2026, 10, 29)):
        updated, _ = store.add_check(claim.id, result, evidence="HTTP 503")
        assert updated.next_check_at == expected
        assert store.due() == []
        clock.now += timedelta(days=1)


@pytest.mark.parametrize("conclusive", [CheckResult.SAME, CheckResult.CHANGED])
def test_a_conclusive_check_resets_the_count(store, claim, clock, conclusive):
    for _ in range(3):
        store.add_check(claim.id, CheckResult.ERROR)  # the third moves it out: 10-19
    updated, _ = store.add_check(claim.id, conclusive, "2.3.0", "2.3.0")
    assert updated.next_check_at == date(2026, 10, 19)
    clock.now += timedelta(days=7)  # 10-19: due again; the count starts from zero
    for expected in (date(2026, 10, 19), date(2026, 10, 19), date(2026, 10, 26)):
        updated, _ = store.add_check(claim.id, CheckResult.ERROR)
        assert updated.next_check_at == expected


def test_the_count_is_per_claim(store, claim):
    other = store.remember("The latest x is 1.0", "world_fact", value="1.0", **PYPI)
    store.add_check(other.id, CheckResult.ERROR)
    store.add_check(other.id, CheckResult.ERROR)
    updated, _ = store.add_check(claim.id, CheckResult.ERROR)  # its first: stays due
    assert updated.next_check_at == date(2026, 10, 8)
    assert claim.id in [c.id for c in store.due()]


def test_a_check_reschedules_by_the_claims_own_class_interval(store):
    medium = store.remember(
        "mcp 2.3.0",
        "world_fact",
        value="2.3.0",
        observed_at="2026-09-01",
        **(PYPI | {"volatility": "medium"}),
    )
    updated, _ = store.add_check(medium.id, CheckResult.SAME, "2.3.0", "2.3.0")
    assert updated.next_check_at == date(2026, 11, 11)  # 10-12 + 30
    for _ in range(3):
        updated, _ = store.add_check(medium.id, CheckResult.ERROR)
    assert updated.next_check_at == date(2026, 11, 11)  # the third error: 10-12 + 30 too


def test_check_times_are_stored_in_utc_and_the_check_date_is_local(store, claim, clock):
    clock.now = datetime(2026, 10, 13, 8, 0, 0, 123456, tzinfo=timezone(timedelta(hours=9)))
    updated, check = store.add_check(claim.id, CheckResult.SAME, "2.3.0", "2.3.0")
    assert check.checked_at == updated.last_checked_at == datetime(2026, 10, 12, 23, 0, tzinfo=UTC)
    [(raw,)] = store._conn.execute("SELECT checked_at FROM checks WHERE id = ?", (check.id,))
    assert raw == "2026-10-12T23:00:00+00:00"
    assert updated.next_check_at == date(2026, 10, 20)  # local date 10-13 + 7, not UTC 10-12


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
