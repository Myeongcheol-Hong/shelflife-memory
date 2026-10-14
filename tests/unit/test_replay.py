from collections import Counter
from dataclasses import astuple
from datetime import date
from pathlib import Path

import pytest

from eval.replay import score
from eval.replay.replay import (
    POLICIES,
    QUESTION_RATES,
    SPLITS,
    Claim,
    Counts,
    Row,
    Truth,
    changes_per_year,
    claims,
    interval,
    outcome,
    replay,
    sessions,
    stream,
    truth,
)
from eval.replay.timelines import load_all, load_projects

ROOT = Path(__file__).parents[2] / "eval" / "data"
SMOKE = load_all(ROOT / "smoke" / "timelines")
# The smoke projects are synthetic and their labels in eval/data/ stay empty: the tests
# supply these (D12).
SMOKE_LABELS = {
    "smoke-backport": "fast",
    "smoke-prerelease-only": "medium",
    "smoke-quiet": "slow",
    "smoke-org/moved-tag": "fast",
    "smoke-org/out-of-order": "medium",
    "smoke-org/two-products": "slow",
}
WEEKLY = QUESTION_RATES["1 a week"]


def d(month, day):
    return date(2024, month, day)


TRUTH = Truth(days=(d(1, 10), d(1, 20)), values=("2.0", "3.0"), before="1.0")


def claim(questions=(), created=None, end=None, label="fast"):
    return Claim("x", label, created or d(1, 1), end or d(1, 31), tuple(questions))


def test_outcome_counts_stale_days_stale_answers_and_detection_delays():
    c = outcome(claim([d(1, 5), d(1, 12), d(1, 25)]), TRUTH, checks=[d(1, 15)])
    assert c == Counts(
        claims=1,
        questions=3,
        stale_answers=2,  # 1-12 (2.0 is out, not checked yet) and 1-25 (3.0 is out)
        days=30,
        stale_days=5 + 12,  # 1-10 to 1-14, then 1-20 to 1-31
        checks=1,
        detected=1,
        delay_days=5,  # 2.0 on 1-10, found 1-15
        undetected=1,  # 3.0 on 1-20, never found
    )
    # A check on a change day sees that day's state and runs before its questions.
    c = outcome(claim([d(1, 10)]), TRUTH, checks=[d(1, 10), d(1, 20)])
    assert (c.stale_answers, c.stale_days, c.delay_days, c.undetected) == (0, 0, 0, 0)


def test_each_policy_checks_on_the_days_it_says():
    medium = claim([d(1, 3), d(1, 9)], end=d(3, 31), label="medium")

    def days(policy, c=medium):
        return POLICIES[policy](c, TRUTH, stream("test"))

    assert days("never") == []
    assert days("every read") == [d(1, 3), d(1, 9)]
    assert days("oracle") == [d(1, 10), d(1, 20)]
    assert days("fixed 30") == [d(1, 31), d(3, 1), d(3, 31)]
    assert days("per-class") == days("fixed 30")  # medium: 30 days (design 4.2)
    assert days("fixed 7")[:3] == [d(1, 8), d(1, 15), d(1, 22)]
    assert days("oracle", claim(created=d(1, 10))) == [d(1, 20)]  # after the creation only
    assert days("oracle", claim(end=d(1, 20))) == [d(1, 10), d(1, 20)]  # the last day too


@pytest.mark.parametrize(("days", "j"), [(3, 0), (7, 1), (14, 1), (15, 2), (30, 3), (180, 18)])
def test_jitter_moves_each_check_by_a_tenth_of_the_interval_rounded_half_up(days, j):
    c = claim(end=date(2100, 1, 1))
    checks = interval(days, jitter=True)(c, TRUTH, stream("jitter", days))
    gaps = {(b - a).days for a, b in zip([c.created, *checks], checks, strict=False)}
    assert gaps <= set(range(days - j, days + j + 1))
    # Drawn anew for every check: over 76 years every offset shows up, the ends included.
    assert gaps == set(range(days - j, days + j + 1)) if days <= 30 else len(gaps) > j


def test_claims_start_on_the_first_day_with_a_latest_and_repeat_exactly():
    late = Truth(days=(d(3, 1), d(6, 1)), values=("0.1", "0.2"), before=None)
    made = claims("x", "fast", late, "dev", seed=7, rate=WEEKLY)
    assert len(made) == 20
    assert all(d(3, 1) <= c.created < d(12, 31) for c in made)
    assert all(c.created < q <= c.end == d(12, 31) for c in made for q in c.questions)
    assert made == claims("x", "fast", late, "dev", seed=7, rate=WEEKLY)
    daily = claims("x", "fast", late, "dev", seed=7, rate=1.0)
    assert [c.created for c in daily] == [c.created for c in made]  # the rate moves no claim
    assert all(len(c.questions) == (c.end - c.created).days for c in daily)
    assert claims("x", "fast", Truth((), (), None), "dev", seed=7, rate=WEEKLY) == []
    # sha256, not hash(): the same draws in every process and on every Python
    assert stream(0, "dev", "x", 0).random() == 0.820566744119386


def test_replay_refuses_a_project_without_a_label():
    with pytest.raises(ValueError, match="no volatility label"):
        replay(SMOKE, SMOKE_LABELS | {"smoke-quiet": ""}, "dev", [0], WEEKLY)


def test_sessions_make_days_of_ten_projects_each_spread_like_the_uniform_scenario():
    truths = {f"p{i}": Truth((), (), "1.0") for i in range(29)}
    truths["young"] = Truth((d(7, 1),), ("0.1",), None)  # a first release mid-split
    placed = sessions(truths, "dev", seed=3)
    assert placed == sessions(truths, "dev", seed=3) != sessions(truths, "dev", seed=4)
    assert all(len(days) == 20 for days in placed.values())  # every claim placed
    per_day = Counter(day for days in placed.values() for day in days)
    assert all(n % 10 == 0 for n in per_day.values())  # 10 a session; two may share a day
    assert min(placed["young"]) >= d(7, 1)
    # Spread over its own window, not bunched after its first release: over 10 seeds, the
    # first quarter of 2024-07-01 to 2024-12-31 holds no more than a quarter of its 200
    # claims. Placing the fewest-placed project first would put 62 there.
    early = [sum(day < d(8, 16) for day in sessions(truths, "dev", s)["young"]) for s in range(10)]
    assert sum(early) <= 50


def test_sessions_drop_a_claim_no_session_can_take():
    truths = {f"p{i}": Truth((), (), "1.0") for i in range(11)}
    truths["late"] = Truth((d(12, 20),), ("0.1",), None)  # a few sessions left in dev
    placed = sessions(truths, "dev", seed=0)
    # 24 sessions of 10 for 11 early projects: never more than 20 claims each.
    assert all(len(placed[f"p{i}"]) == 20 for i in range(11))
    assert 0 < len(placed["late"]) < 20  # at most one claim per session
    assert sessions({"none": Truth((), (), None)}, "dev", seed=0) == {}


def test_claims_take_the_placed_days_and_their_questions_come_after():
    made = claims("x", "fast", Truth((), (), "1.0"), "dev", 0, 1.0, placed=[d(3, 1), d(12, 30)])
    assert [c.created for c in made] == [d(3, 1), d(12, 30)]
    assert [len(c.questions) for c in made] == [(SPLITS["dev"][1] - d(3, 1)).days, 1]


def test_changes_per_year_leaves_out_a_first_release():
    late = Truth((d(3, 1), d(6, 1)), ("0.1", "0.2"), None)
    assert changes_per_year(late, "dev") == pytest.approx(1 / (306 / 365))
    assert changes_per_year(Truth((d(1, 10), d(1, 20)), ("2", "3"), "1"), "dev") == pytest.approx(
        2 / (366 / 365)  # 2024 is a leap year
    )
    assert changes_per_year(Truth((), (), None), "dev") == 0.0


def test_peak_ci_resamples_projects_and_pairs_the_policies():
    def row(seed, project, policy, *days):
        return Row(seed, project, policy, Counts(claims=1), Counter(days))

    rows = [row(0, "p", "x", d(1, 2), d(1, 2)), row(0, "q", "x", d(1, 2))]
    rows += [row(0, "p", "y", d(1, 2)), row(0, "q", "y", d(1, 3))]
    assert score.peak_ci(rows, "x", "dev", minus="x") == (0, 0)
    assert score.peak_ci(rows, "x", "dev") == (2, 4)  # two q's give 2, two p's give 4
    assert score.peak_ci(rows, "x", "dev", minus="y")[1] > 0
    # With a second seed the peak is averaged over the seeds: two p's give (4 + 2) / 2.
    rows += [row(1, "p", "x", d(1, 2)), row(1, "q", "x", d(1, 2))]
    assert score.peak_ci(rows, "x", "dev") == (2, 3)


@pytest.fixture(scope="module")
def real():
    timelines = load_all(ROOT / "timelines")
    projects = load_projects(ROOT / "timelines" / "projects.toml")
    return timelines, {p.name: p.volatility for p in projects}


def test_per_class_with_every_label_fast_is_fixed_7_exactly(real):
    timelines, labels = real
    fast = dict.fromkeys(labels, "fast")
    policies = {name: POLICIES[name] for name in ("fixed 7", "per-class")}
    rows = replay(timelines, fast, "dev", [0], WEEKLY, policies)
    by = {(r.project, r.policy): (r.counts, r.daily) for r in rows}
    assert all(by[t.project, "per-class"] == by[t.project, "fixed 7"] for t in timelines)


def test_the_latest_never_returns_to_an_earlier_value(real):
    # So a stored value is stale exactly when the latest changed since it was read (D12).
    for t in real[0]:
        for split in SPLITS:
            tr = truth(t, split)
            seen = [tr.before, *tr.values]
            assert len(set(seen)) == len(seen), (t.project, split)


def test_scores_are_ratios_of_summed_counts_and_resample_whole_projects():
    a = Counts(claims=1, questions=4, stale_answers=1)
    b = Counts(claims=1, questions=6, stale_answers=4)
    rows = [Row(0, "p", "x", a, Counter()), Row(1, "p", "x", b, Counter())]
    rows.append(Row(0, "young", "x", Counts(), Counter()))  # no claim in this split
    assert score.per_project(rows, "x") == {"p": Counts(1, questions=5, stale_answers=2.5)}
    c = Counts(1, 4, 1, days=60, stale_days=6, checks=3, detected=4, delay_days=10, undetected=1)
    assert {m: score.value(m, c) for m in score.METRICS} == {
        "stale-answer rate": 0.25,
        "stale claim-days": 0.1,
        "checks per claim-month": 1.5,
        "mean days to detect": 2.5,
        "undetected share": 0.2,
    }
    assert score.value("stale-answer rate", a + b) == 0.5
    assert score.value("mean days to detect", a) is None
    same = {"p": a, "q": a}
    assert score.ci("stale-answer rate", same) == (0.25, 0.25)
    assert score.ci("stale-answer rate", {"p": a, "q": b}, minus={"p": a, "q": b}) == (0, 0)
    assert score.percentiles(list(range(2000, 0, -1))) == (50, 1950)  # nearest rank


def test_peak_is_the_busiest_day_per_seed_then_averaged():
    rows = [
        Row(0, "p", "x", Counts(), Counter({d(1, 2): 3, d(1, 3): 1})),
        Row(0, "q", "x", Counts(), Counter({d(1, 2): 2})),
        Row(1, "p", "x", Counts(), Counter({d(5, 1): 4})),
    ]
    days = (SPLITS["dev"][1] - SPLITS["dev"][0]).days + 1
    assert score.peak(rows, "x", "dev") == (4.5, (5 * days / 6 + 4 * days / 4) / 2)


def test_the_smoke_run_gives_the_pinned_counts():
    # Pinned so a change to any draw or rule shows, on Python 3.11 and 3.13 alike (D12).
    rows = replay(SMOKE, SMOKE_LABELS, "test", [0, 1, 2, 3, 4], WEEKLY)
    found = {}
    for name in POLICIES:
        c = score.total(score.per_project(rows, name))
        found[name] = tuple(round(x * 5) for x in astuple(c))  # summed over the 5 seeds
    assert found == PINNED
    projects = score.per_project(rows, "per-class")
    lo, hi = score.ci("stale claim-days", projects, minus=score.per_project(rows, "fixed 30"))
    assert (round(lo, 6), round(hi, 6)) == PINNED_INTERVAL


# Every count, summed over the 5 seeds: claims, questions, stale answers, claim-days, stale
# claim-days, checks, detected changes, their delay days, undetected changes.
PINNED = {
    "never": (600, 26380, 3828, 186291, 27150, 0, 0, 0, 53),
    "every read": (600, 26380, 0, 186291, 288, 26380, 53, 288, 0),
    "oracle": (600, 26380, 0, 186291, 0, 53, 53, 0, 0),
    "fixed 3": (600, 26380, 11, 186291, 56, 61904, 53, 56, 0),
    "fixed 7": (600, 26380, 22, 186291, 160, 26357, 53, 160, 0),
    "fixed 14": (600, 26380, 43, 186291, 314, 13024, 53, 314, 0),
    "fixed 30": (600, 26380, 118, 186291, 806, 5911, 53, 806, 0),
    "fixed 60": (600, 26380, 244, 186291, 1766, 2814, 53, 1766, 0),
    "fixed 90": (600, 26380, 419, 186291, 2996, 1769, 53, 2996, 0),
    "fixed 180": (600, 26380, 854, 186291, 6326, 758, 53, 6326, 0),
    "per-class": (600, 26380, 435, 186291, 3318, 11135, 53, 3318, 0),
    "per-class + jitter": (600, 26380, 435, 186291, 3307, 11133, 53, 3307, 0),
    "fixed 7 + jitter": (600, 26380, 25, 186291, 188, 26373, 53, 188, 0),
    "fixed 30 + jitter": (600, 26380, 114, 186291, 837, 5922, 53, 837, 0),
}
PINNED_INTERVAL = (-0.003545, 0.041518)
