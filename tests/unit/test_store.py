import sqlite3
import threading
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from shelflife.models import CheckMethod, CheckResult, FieldSource, Status, Volatility
from shelflife.store import Store, default_db_path, query_words

# --- remember -------------------------------------------------------------------------


def test_remember_minimal_world_fact_gets_defaults(store):
    claim = store.remember("Seoul has 25 districts", "world_fact")  # no rule applies

    assert len(claim.id) == 12
    assert claim.volatility is Volatility.FAST
    assert claim.volatility_source is FieldSource.DEFAULT
    assert claim.check_method is CheckMethod.NONE
    assert claim.check_method_source is FieldSource.DEFAULT
    assert claim.status is Status.UNVERIFIABLE  # a world fact nothing can check
    assert claim.observed_at == date(2026, 10, 12)
    assert claim.recorded_at == datetime(2026, 10, 12, 9, 30, tzinfo=UTC)
    assert claim.next_check_at == date(2026, 10, 19)
    assert store.get(claim.id) == claim


def test_remember_keeps_caller_fields_and_marks_their_source(store):
    given = {
        "subject": "mcp (PyPI)",
        "attribute": "latest_version",
        "value": "2.3.0",
        "volatility": "medium",
        "check_method": "pypi",
        "check_target": "mcp",
        "source_url": "https://pypi.org/project/mcp/",
        "source_quote": "mcp 2.3.0",
        "observed_at": "2026-10-01",
    }
    claim = store.remember("The latest mcp on PyPI is 2.3.0", "world_fact", **given)

    stored = store.get(claim.id).to_dict()
    assert {k: stored[k] for k in given} == given  # every input lands in its own column
    assert (claim.volatility, claim.volatility_source) == (Volatility.MEDIUM, FieldSource.CALLER)
    assert (claim.check_method, claim.check_method_source) == (
        CheckMethod.PYPI,
        FieldSource.CALLER,
    )
    assert claim.status is Status.FRESH
    assert claim.next_check_at == date(2026, 10, 31)  # from observed_at, not from today
    assert store.get(claim.id) == claim


@pytest.mark.parametrize("kind", ["decision", "preference", "note"])
def test_remember_non_facts_default_to_never_checked(store, kind):
    claim = store.remember("Use SQLite", kind)
    assert claim.volatility is Volatility.NONE
    assert claim.next_check_at is None
    assert claim.status is Status.FRESH


def test_remember_treats_blank_strings_as_missing(store):
    claim = store.remember("  A fact  ", "world_fact", volatility="", check_method=" ", value="")
    assert claim.text == "A fact"
    assert claim.volatility_source is FieldSource.DEFAULT
    assert claim.check_method_source is FieldSource.DEFAULT
    assert claim.value is None


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"text": " "}, "text must not be empty"),
        ({"kind": "fact"}, "kind must be one of: world_fact, decision, preference, note"),
        ({"volatility": "daily"}, "volatility must be one of: fast, medium, slow, none"),
        ({"check_method": "rss"}, "check_method must be one of"),
        ({"check_method": "pypi"}, "check_target is required when check_method is pypi"),
        ({"observed_at": "2026/10/08"}, "observed_at must be a date in YYYY-MM-DD form"),
        ({"observed_at": "2026-10-08T10:00:00"}, "YYYY-MM-DD"),
        ({"observed_at": "2026-02-30"}, "observed_at is not a valid date"),
        ({"observed_at": "2026-10-14"}, "observed_at is in the future"),
        ({"depends_on": ["x"]}, "depends_on is only allowed on decision claims"),
        ({"kind": "decision", "depends_on": "x"}, "depends_on must be a list"),
        ({"status": "fresh", "id": "x"}, r"unknown or system-managed field\(s\): id, status"),
        ({"value": 300}, "value must be a string"),
        (
            {"kind": "preference", "check_method": "web_page", "check_target": "https://a.b"},
            "preference claims are never checked",
        ),
    ],
)
def test_remember_rejects_invalid_input(store, kwargs, message):
    args = {"text": "A fact", "kind": "world_fact"} | kwargs
    with pytest.raises(ValueError, match=message):
        store.remember(**args)


def test_decision_depends_on_existing_claims(store):
    fact = store.remember("MemGuard has not published eval results", "world_fact")
    decision = store.remember("Focus on the eval", "decision", depends_on=[fact.id, fact.id])
    assert decision.depends_on == (fact.id,)
    assert store.get(decision.id).depends_on == (fact.id,)


def test_unknown_dependency_is_rejected_and_nothing_is_written(store):
    with pytest.raises(ValueError, match="unknown claim 'missing'"):
        store.remember("Focus on the eval", "decision", depends_on=["missing"])
    assert store.recall("eval") == []


# --- recall ---------------------------------------------------------------------------


def test_recall_matches_text_and_subject_case_insensitively(store):
    fee = store.remember("The exam fee is $300", "world_fact", subject="AWS AIP-C01")
    store.remember("Code is written in English", "preference")

    assert [c.id for c in store.recall("EXAM")] == [fee.id]
    assert [c.id for c in store.recall("aip-c01")] == [fee.id]
    assert [c.id for c in store.recall("AI")] == [fee.id]  # short word, subject only
    assert store.recall("python") == []


def test_recall_ranks_better_matches_first(store):
    weak = store.remember("The mcp package exists", "note")
    strong = store.remember("The latest mcp package version is 2.3.0", "world_fact")
    assert [c.id for c in store.recall("latest mcp version")] == [strong.id, weak.id]


@pytest.mark.parametrize("query", ['mcp" OR (', "NEAR(a b)", "*", "subject:mcp", "", "-"])
def test_recall_never_interprets_fts_syntax(store, query):
    store.remember("The mcp package", "note")
    store.recall(query)  # must not raise sqlite3.OperationalError


def test_recall_treats_operators_as_plain_words(store):
    claim = store.remember("The exam is not free", "world_fact")
    assert [c.id for c in store.recall("exam NOT free")] == [claim.id]
    assert [c.id for c in store.recall('free" OR (')] == [claim.id]


# Korean (D8): particles fuse onto words ("Chatbox로", "가격은"), and many Korean words
# are shorter than a trigram.
KOREAN = {
    "decision": "멀티 LLM 앱은 Chatbox로 정했다",
    "price": "Chatbox Pro 가격은 월 $19.99이다",
    "exam": "AWS AIP-C01 시험 비용은 $300이다",
}


@pytest.fixture
def korean(store):
    return {store.remember(text, "note").id: name for name, text in KOREAN.items()}


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Chatbox 가격", ["price", "decision"]),  # two words matched before one
        ("시험 비용", ["exam"]),  # both words shorter than a trigram
        ("aip-c01 시험", ["exam"]),
        ("챗박스", []),  # a name is found only in its original spelling
    ],
)
def test_recall_finds_korean_claims(store, korean, query, expected):
    assert [korean[c.id] for c in store.recall(query)] == expected


@pytest.mark.parametrize(
    ("query", "words"),
    [
        ("Chatbox의 가격", ["Chatbox", "가격"]),  # particle after a Latin name: dropped
        ("Hindsight에서", ["Hindsight"]),
        ("GPT4는", ["GPT4"]),
        ("AI모델", ["AI", "모델"]),  # not a particle: both parts kept
        ("AI모델v2", ["AI", "모델", "v2"]),  # split at every boundary
        ("모델v2", ["모델", "v2"]),  # Hangul first
        ("Chatbox로 chatbox", ["Chatbox"]),  # deduplicated ignoring case
        ("가격은", ["가격은"]),  # Hangul only: not split
        ("3월", ["3월"]),  # no Latin letter: not split
    ],
)
def test_query_words_split_latin_and_hangul(query, words):
    assert query_words(query) == words


# The owner's list (D8), written out here so a change to PARTICLES fails a test.
@pytest.mark.parametrize(
    "particle",
    ["은", "는", "이", "가", "을", "를", "의", "로", "으로", "에", "에서", "와", "과", "도", "만"],
)
def test_query_words_drop_each_listed_particle(particle):
    assert query_words("Chatbox" + particle) == ["Chatbox"]


def test_recall_drops_a_particle_after_a_latin_name(store, korean):
    assert [korean[c.id] for c in store.recall("Chatbox의 가격은")] == ["price", "decision"]


def test_recall_keeps_a_hangul_part_that_is_not_a_particle(store):
    both = store.remember("새 AI 모델 비교", "note")
    one = store.remember("모델 목록", "note")
    assert [c.id for c in store.recall("AI모델")] == [both.id, one.id]


def test_recall_finds_a_latin_name_with_a_korean_particle_attached(store, korean):
    assert {korean[c.id] for c in store.recall("chatbox")} == {"decision", "price"}


def test_recall_ranks_more_matched_words_above_a_common_short_word(store):
    for i in range(12):
        store.remember(f"가격 메모 {i}", "note")
    target = store.remember("Chatbox Pro 가격은 월 $19.99이다", "world_fact")
    assert store.recall("Chatbox 가격")[0].id == target.id


def test_recall_breaks_equal_word_counts_by_bm25(store):
    # Ids sort opposite to the bm25 order, so ranking without bm25 fails every time.
    store.import_claims(
        [
            {
                "id": "a",
                "text": "chatbox appears once in this long note about other apps",
                "kind": "note",
            },
            {"id": "b", "text": "chatbox chatbox", "kind": "note"},
        ]
    )
    assert [c.id for c in store.recall("chatbox")] == ["b", "a"]


def test_recall_keeps_the_spelling_of_short_non_ascii_words(store):
    claim = store.remember("ЕС санкции", "note")  # LIKE folds ASCII case only
    assert [c.id for c in store.recall("ЕС")] == [claim.id]


def test_recall_like_fallback_treats_underscore_literally(store):
    snake = store.remember("snake_case names", "note")
    store.remember("snakeXcase names", "note")
    assert [c.id for c in store.recall("e_")] == [snake.id]


def test_recall_respects_limit(store):
    for i in range(5):
        store.remember(f"Claim number {i} about pricing", "note")
    assert len(store.recall("pricing", limit=3)) == 3


# --- due ------------------------------------------------------------------------------


def test_due_lists_checkable_claims_past_next_check_at(store, clock):
    pypi = {"check_method": "pypi", "check_target": "mcp", "volatility": "fast"}
    old = store.remember("Old version", "world_fact", observed_at="2026-10-01", **pypi)
    recent = store.remember("New version", "world_fact", observed_at="2026-10-10", **pypi)

    assert [c.id for c in store.due()] == [old.id]  # 2026-10-08 <= 2026-10-12
    assert [c.id for c in store.due(days=5)] == [old.id, recent.id]  # 10-17 <= 10-17

    clock.now += timedelta(days=30)
    assert [c.id for c in store.due()] == [old.id, recent.id]


def test_due_leaves_out_claims_nothing_can_check(store, clock):
    store.remember("A fee with no check method", "world_fact", observed_at="2026-09-01")
    store.remember("I like short answers", "preference", volatility="fast")
    clock.now += timedelta(days=365)
    assert store.due() == []


def test_dates_follow_the_clocks_time_zone(store, clock):
    clock.now = datetime(2026, 10, 13, 8, 0, 0, 123456, tzinfo=timezone(timedelta(hours=9)))
    fact = store.remember(
        "A version", "world_fact", check_method="pypi", check_target="x", observed_at="2026-10-06"
    )
    note = store.remember("A note", "note")

    assert note.observed_at == date(2026, 10, 13)  # local date, not UTC (still 10-12)
    assert note.recorded_at == datetime(2026, 10, 12, 23, 0, tzinfo=UTC)
    [(raw,)] = store._conn.execute("SELECT recorded_at FROM claims WHERE id = ?", (note.id,))
    assert raw == "2026-10-12T23:00:00+00:00"
    assert [c.id for c in store.due()] == [fact.id]  # next_check_at 10-13 is local today


def test_changed_lists_claims_whose_last_check_found_a_new_value(store, clock):
    pypi = {"check_method": "pypi", "check_target": "mcp", "value": "1.0"}
    first = store.remember("First version", "world_fact", **pypi)
    second = store.remember("Second version", "world_fact", **pypi)
    store.remember("Third version", "world_fact", **pypi)  # never checked
    store.add_check(first.id, CheckResult.CHANGED, "2.0", "2.0")
    clock.now += timedelta(hours=1)
    store.add_check(second.id, CheckResult.CHANGED, "2.0", "2.0")
    assert [c.id for c in store.changed()] == [second.id, first.id]  # newest check first

    store.add_check(first.id, CheckResult.SAME, "1.0", "1.0")  # the source went back
    assert [c.id for c in store.changed()] == [second.id]


def test_needs_check_method_lists_world_facts_nothing_can_check(store, clock):
    first = store.remember("Seoul has 25 districts", "world_fact")
    clock.now += timedelta(minutes=1)
    second = store.remember("A fee with no check method", "world_fact")
    store.remember("A version", "world_fact", check_method="pypi", check_target="x")
    store.remember("I like short answers", "preference")
    store.remember("A note", "note")
    retired = store.remember("A forgotten fact", "world_fact")
    store.forget(retired.id)
    assert [c.id for c in store.needs_check_method()] == [first.id, second.id]


def test_due_rejects_bad_days(store):
    with pytest.raises(ValueError, match="days must be 0 or more"):
        store.due(days=-1)
    with pytest.raises(ValueError, match="days is too large"):
        store.due(days=10**7)


# --- database file --------------------------------------------------------------------


def test_claims_survive_reopening(tmp_path, clock):
    path = tmp_path / "nested" / "shelflife.db"
    with Store(path, now=clock) as s:
        claim = s.remember("A fact", "world_fact")
    with Store(path, now=clock) as s:
        assert s.get(claim.id) == claim
        assert [c.id for c in s.recall("fact")] == [claim.id]


def test_connection_uses_wal_and_a_busy_timeout(store):
    assert store._conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert store._conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_switch_to_wal_waits_for_another_writer(tmp_path, clock):
    # A second process creating the schema holds a write lock; the WAL switch does not
    # use the busy handler, so the store must retry instead of failing at once.
    path = tmp_path / "shelflife.db"
    other = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    other.execute("CREATE TABLE other (x)")
    other.execute("BEGIN IMMEDIATE")
    threading.Timer(0.3, lambda: other.execute("COMMIT")).start()
    with Store(path, now=clock) as s:
        assert s._conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    other.close()


def test_schema_creation_is_idempotent(tmp_path, clock):
    # Two processes opening a new file at once can both see user_version 0.
    path = tmp_path / "shelflife.db"
    with Store(path, now=clock) as s:
        claim = s.remember("A fact", "world_fact")
        s._conn.execute("PRAGMA user_version = 0")
    with Store(path, now=clock) as s:
        assert s.get(claim.id) == claim


def test_unknown_schema_version_is_refused(tmp_path):
    path = tmp_path / "shelflife.db"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA user_version = 99")
    conn.close()
    with pytest.raises(RuntimeError, match="schema version 99"):
        Store(path)


def test_naive_clock_is_refused(tmp_path):
    with Store(tmp_path / "db", now=lambda: datetime(2026, 10, 12)) as s:
        with pytest.raises(ValueError, match="timezone-aware"):
            s.remember("A fact", "world_fact")


def test_db_path_comes_from_env_or_home(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELFLIFE_DB", str(tmp_path / "x.db"))
    assert default_db_path() == tmp_path / "x.db"
    monkeypatch.delenv("SHELFLIFE_DB")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert default_db_path() == tmp_path / ".shelflife" / "shelflife.db"
