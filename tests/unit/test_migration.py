"""Schema v1 to v2 (D10): a one-way door, so the v1 file is backed up first."""

import sqlite3
from contextlib import closing

import pytest
from mcp import Client

from shelflife.models import CheckResult
from shelflife.server import build_server
from shelflife.store import Store

# The v1 schema as main shipped it before schema v2, copied verbatim.
V1_SCHEMA = """
BEGIN;
CREATE TABLE IF NOT EXISTS claims (
  id            TEXT PRIMARY KEY,
  text          TEXT NOT NULL,
  kind          TEXT NOT NULL,          -- world_fact | decision | preference | note
  subject       TEXT, attribute TEXT, value TEXT,
  volatility    TEXT NOT NULL,          -- fast | medium | slow | none
  volatility_source   TEXT NOT NULL,    -- caller | default | rule
  check_method  TEXT NOT NULL,          -- pypi | github_release | web_page | none
  check_method_source TEXT NOT NULL,    -- caller | default | rule
  check_target  TEXT,
  source_url    TEXT, source_quote TEXT,
  observed_at   TEXT NOT NULL,          -- ISO 8601 date
  recorded_at   TEXT NOT NULL,          -- ISO 8601 UTC timestamp
  last_checked_at TEXT, next_check_at TEXT,
  status        TEXT NOT NULL DEFAULT 'fresh'
);
CREATE TABLE IF NOT EXISTS depends_on (
  decision_id TEXT, claim_id TEXT, PRIMARY KEY (decision_id, claim_id)
);
CREATE TABLE IF NOT EXISTS checks (
  id TEXT PRIMARY KEY, claim_id TEXT NOT NULL, checked_at TEXT NOT NULL,
  method TEXT NOT NULL, result TEXT NOT NULL,   -- same | changed | cannot_tell | error
  old_value TEXT, new_value TEXT, evidence TEXT, cost_usd REAL
);
CREATE VIRTUAL TABLE IF NOT EXISTS claims_fts
  USING fts5(text, subject, content='claims', tokenize='trigram');
CREATE TRIGGER IF NOT EXISTS claims_ai AFTER INSERT ON claims BEGIN
  INSERT INTO claims_fts(rowid, text, subject) VALUES (new.rowid, new.text, new.subject);
END;
CREATE TRIGGER IF NOT EXISTS claims_ad AFTER DELETE ON claims BEGIN
  INSERT INTO claims_fts(claims_fts, rowid, text, subject)
    VALUES ('delete', old.rowid, old.text, old.subject);
END;
CREATE TRIGGER IF NOT EXISTS claims_au AFTER UPDATE OF text, subject ON claims BEGIN
  INSERT INTO claims_fts(claims_fts, rowid, text, subject)
    VALUES ('delete', old.rowid, old.text, old.subject);
  INSERT INTO claims_fts(rowid, text, subject) VALUES (new.rowid, new.text, new.subject);
END;
PRAGMA user_version = 1;
COMMIT;
"""

CLAIM = {
    "id": "c1",
    "text": "The AWS AIP-C01 exam fee is $300",
    "kind": "world_fact",
    "value": "$300",
    "volatility": "fast",
    "volatility_source": "caller",
    "check_method": "web_page",
    "check_method_source": "caller",
    "check_target": "https://example.com/exam",
    "observed_at": "2026-10-01",
    "recorded_at": "2026-10-01T00:00:00+00:00",
    "last_checked_at": "2026-10-05T00:00:00+00:00",
    "next_check_at": "2026-10-12",
    "status": "fresh",
}
CHECK = (
    "k1",
    "c1",
    "2026-10-05T00:00:00+00:00",
    "web_page",
    "same",
    "$300",
    None,
    "Exam fee: $300",
)


@pytest.fixture
def v1_file(tmp_path):
    """A v1 database in WAL mode whose last write is still in the -wal file: the
    connection that wrote it stays open, so nothing has been checkpointed."""
    path = tmp_path / "shelflife.db"
    writer = sqlite3.connect(path)
    writer.execute("PRAGMA journal_mode = WAL")
    writer.executescript(V1_SCHEMA)
    writer.execute("PRAGMA wal_autocheckpoint = 0")
    columns = ", ".join(CLAIM)
    writer.execute(
        f"INSERT INTO claims ({columns}) VALUES ({', '.join('?' * len(CLAIM))})",
        tuple(CLAIM.values()),
    )
    writer.execute(
        "INSERT INTO checks (id, claim_id, checked_at, method, result, old_value, new_value,"
        " evidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        CHECK,
    )
    writer.commit()
    assert path.with_name("shelflife.db-wal").stat().st_size > 0
    yield path
    writer.close()


def columns(conn, table):
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def test_a_v1_file_is_backed_up_then_migrated(v1_file, clock, capsys):
    with Store(v1_file, now=clock) as store:
        assert store._conn.execute("PRAGMA user_version").fetchone()[0] == 2
        assert columns(store._conn, "checks")[-4:] == [
            "prompt_version",
            "page_sha256",
            "section_sha256",
            "reason",
        ]
        check = store.last_check("c1")
        assert (check.result, check.evidence, check.reason) == (
            CheckResult.SAME,
            "Exam fee: $300",
            None,
        )
        assert store.get("c1").value == "$300"

    backup = v1_file.with_name("shelflife.db.bak-v1")
    with closing(sqlite3.connect(backup)) as copy:
        assert copy.execute("PRAGMA user_version").fetchone()[0] == 1
        assert copy.execute("PRAGMA journal_mode").fetchone()[0] == "delete"  # one file
        assert "reason" not in columns(copy, "checks")
        assert copy.execute("SELECT id FROM claims").fetchall() == [("c1",)]  # from the -wal
        assert copy.execute("SELECT id FROM checks").fetchall() == [("k1",)]
    assert not backup.with_name("shelflife.db.bak-v1-wal").exists()
    err = capsys.readouterr().err
    assert f"database upgraded to schema v2; the v1 file is saved as {backup}" in err


def test_a_migrated_file_is_not_migrated_again(v1_file, clock, capsys):
    Store(v1_file, now=clock).close()
    backup = v1_file.with_name("shelflife.db.bak-v1")
    saved = backup.read_bytes()
    capsys.readouterr()
    with Store(v1_file, now=clock) as store:
        assert store._conn.execute("PRAGMA user_version").fetchone()[0] == 2
    assert capsys.readouterr().err == ""
    assert backup.read_bytes() == saved


def test_a_new_check_stores_the_v2_columns(v1_file, clock):
    with Store(v1_file, now=clock) as store:
        _, check = store.add_check(
            "c1",
            CheckResult.CANNOT_TELL,
            prompt_version="j1",
            page_sha256="a" * 64,
            section_sha256="b" * 64,
            reason="login wall",
        )
        stored = store.last_check("c1")
    assert stored == check
    assert (stored.prompt_version, stored.reason) == ("j1", "login wall")


def test_a_process_that_waited_for_the_lock_finds_v2_and_stops(v1_file, clock, capsys):
    # Two servers can both read user_version 1; the second gets the write lock after the
    # first migrated, so it must re-read the version under the lock and do nothing.
    with Store(v1_file, now=clock) as store:
        capsys.readouterr()
        store._migrate_v1()  # what the second process runs once it has the lock
        assert store._conn.execute("PRAGMA user_version").fetchone()[0] == 2
    assert capsys.readouterr().err == ""


@pytest.mark.anyio
async def test_the_next_tool_result_carries_the_upgrade_notice_once(v1_file, clock):
    # Claude tells the user where the backup is (D10 follow-up 15).
    backup = v1_file.with_name("shelflife.db.bak-v1")
    with Store(v1_file, now=clock) as store:
        async with Client(build_server(store, now=clock)) as client:
            first = (await client.call_tool("due", {})).structured_content
            second = (await client.call_tool("due", {})).structured_content
            instructions = " ".join(client.instructions.split())
    assert first["notice"] == f"database upgraded to schema v2; the v1 file is saved as {backup}"
    assert "notice" not in second
    assert "If a result has a notice, pass it on to the user." in instructions


@pytest.fixture
def anyio_backend():
    return "asyncio"
