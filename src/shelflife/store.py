"""SQLite storage for claims (design 5.1), with FTS5 search."""

from __future__ import annotations

import os
import re
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from shelflife import scheduler
from shelflife.models import (
    DEFAULT_VOLATILITY,
    CheckMethod,
    Claim,
    FieldSource,
    Kind,
    Status,
    Volatility,
    parse_enum,
)

Clock = Callable[[], datetime]

# Inputs `remember` accepts besides text and kind.
OPTIONAL_FIELDS = (
    "subject",
    "attribute",
    "value",
    "volatility",
    "check_method",
    "check_target",
    "source_url",
    "source_quote",
    "observed_at",
    "depends_on",
)

SCHEMA_VERSION = 1
BUSY_TIMEOUT_SECONDS = 5

# Design 5.1, plus the *_source columns and the triggers that keep the
# external-content FTS index in sync with the claims table. IF NOT EXISTS lets two
# processes that open a new file at the same moment both succeed. The trigram tokenizer
# matches substrings, so a Korean particle fused onto a word ("Chatbox로") does not hide
# the word (D8).
SCHEMA = """
BEGIN;
CREATE TABLE IF NOT EXISTS claims (
  id            TEXT PRIMARY KEY,
  text          TEXT NOT NULL,
  kind          TEXT NOT NULL,          -- world_fact | decision | preference | note
  subject       TEXT, attribute TEXT, value TEXT,
  volatility    TEXT NOT NULL,          -- fast | medium | slow | none
  volatility_source   TEXT NOT NULL,    -- caller | default | rule | llm
  check_method  TEXT NOT NULL,          -- pypi | github_release | web_page | none
  check_method_source TEXT NOT NULL,    -- caller | default | rule | llm
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


def default_db_path() -> Path:
    """$SHELFLIFE_DB if set, else ~/.shelflife/shelflife.db."""
    env = os.environ.get("SHELFLIFE_DB")
    return Path(env).expanduser() if env else Path.home() / ".shelflife" / "shelflife.db"


def system_clock() -> datetime:
    """Current local time, timezone-aware. Logic takes a clock instead of calling this."""
    return datetime.now().astimezone()


def _clean(value: Any, field_name: str) -> str | None:
    """Strip whitespace and treat empty strings as missing (callers often send "")."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string (got {value!r})")
    return value.strip() or None


def _parse_observed_at(value: str, today: date) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"observed_at must be a date in YYYY-MM-DD form (got {value!r})")
    try:
        observed = date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"observed_at is not a valid date (got {value!r})") from None
    # One day of slack for a caller whose time zone is ahead of the server's.
    if observed > today + timedelta(days=1):
        raise ValueError(f"observed_at is in the future (got {value!r}, today is {today})")
    return observed


class Store:
    """All reads and writes of the SQLite file.

    MCP runs synchronous tools in worker threads, so the connection is shared across
    threads and every public method holds a lock.
    """

    def __init__(self, path: str | Path, now: Clock = system_clock) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        # Claude Desktop and Claude Code each run their own server process on this file.
        # WAL lets readers and a writer work at the same time, and a writer waits for
        # another writer's lock (busy timeout) instead of failing at once.
        self._conn = sqlite3.connect(
            str(path), check_same_thread=False, timeout=BUSY_TIMEOUT_SECONDS
        )
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._clock = now
        try:
            self._enable_wal()
            self._migrate()
        except BaseException:
            self._conn.close()
            raise

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _enable_wal(self) -> None:
        """Switch the file to WAL, retrying for up to the busy timeout.

        The switch does not wait on the busy handler: while another process holds a write
        lock (for example a second server creating the schema in a new file), it fails at
        once with "database is locked".
        """
        deadline = time.monotonic() + BUSY_TIMEOUT_SECONDS
        while True:
            try:
                self._conn.execute("PRAGMA journal_mode = WAL")
                return
            except sqlite3.OperationalError as e:
                if "locked" not in str(e) or time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)

    def _migrate(self) -> None:
        version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            self._conn.executescript(SCHEMA)
        elif version != SCHEMA_VERSION:
            raise RuntimeError(
                f"database schema version {version} is not supported (expected {SCHEMA_VERSION})"
            )

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("the clock must return a timezone-aware datetime")
        return now

    # --- writes -----------------------------------------------------------------------

    def remember(self, text: str, kind: str, **fields: Any) -> Claim:
        """Validate and store a new claim. Raises ValueError on invalid input.

        `fields` may hold any of OPTIONAL_FIELDS. System-managed fields (id, recorded_at,
        last_checked_at, next_check_at, status) are rejected like any unknown key.
        """
        claim = self._new_claim(uuid.uuid4().hex[:12], text, kind, fields)
        with self._lock, self._conn:
            self._insert_row(claim)
            self._insert_depends_on(claim)
        return claim

    def import_claims(self, records: Iterable[Mapping[str, Any]]) -> tuple[int, int]:
        """Store claims that carry their own ids, such as examples/seed_claims.jsonl.

        Records are validated like `remember` input, plus an `id`. Ids already stored are
        skipped, so importing a file twice is harmless. The import is one transaction: if
        any record is invalid, nothing is stored. Returns (imported, skipped).
        """
        claims: list[Claim] = []
        seen: set[str] = set()
        for n, record in enumerate(records, start=1):
            fields = dict(record)
            try:
                claim_id = _clean(fields.pop("id", None), "id")
            except ValueError as e:
                raise ValueError(f"record {n}: {e}") from None
            if claim_id is None:
                raise ValueError(f"record {n}: id is required")
            if claim_id in seen:
                raise ValueError(f"record {n}: duplicate id {claim_id!r}")
            seen.add(claim_id)
            try:
                text, kind = fields.pop("text", None), fields.pop("kind", None)
                claims.append(self._new_claim(claim_id, text, kind, fields))
            except ValueError as e:
                raise ValueError(f"record {n} ({claim_id}): {e}") from None

        with self._lock, self._conn:
            new = [c for c in claims if not self._exists(c.id)]
            for claim in new:  # all rows first, so depends_on may point later in the file
                self._insert_row(claim)
            for claim in new:
                self._insert_depends_on(claim)
        return len(new), len(claims) - len(new)

    def _new_claim(self, claim_id: str, text: str, kind: str, fields: Mapping[str, Any]) -> Claim:
        """Apply validation and defaults. Does not touch the database."""
        unknown = sorted(set(fields) - set(OPTIONAL_FIELDS))
        if unknown:
            raise ValueError(f"unknown or system-managed field(s): {', '.join(unknown)}")
        f = {n: _clean(fields.get(n), n) for n in OPTIONAL_FIELDS if n != "depends_on"}

        text_ = _clean(text, "text")
        if text_ is None:
            raise ValueError("text must not be empty")
        kind_ = parse_enum(Kind, kind, "kind")

        if f["volatility"] is None:
            volatility, volatility_source = DEFAULT_VOLATILITY[kind_], FieldSource.DEFAULT
        else:
            volatility = parse_enum(Volatility, f["volatility"], "volatility")
            volatility_source = FieldSource.CALLER

        if f["check_method"] is None:
            method, method_source = CheckMethod.NONE, FieldSource.DEFAULT
        else:
            method = parse_enum(CheckMethod, f["check_method"], "check_method")
            method_source = FieldSource.CALLER
        if method is not CheckMethod.NONE:
            if kind_ in (Kind.PREFERENCE, Kind.DECISION):
                raise ValueError(f"{kind_} claims are never checked; leave check_method empty")
            if f["check_target"] is None:
                raise ValueError(f"check_target is required when check_method is {method}")

        raw_deps = fields.get("depends_on") or []
        if not isinstance(raw_deps, list | tuple):
            raise ValueError("depends_on must be a list of claim ids")
        deps = tuple(dict.fromkeys(d for d in (_clean(d, "depends_on") for d in raw_deps) if d))
        if deps and kind_ is not Kind.DECISION:
            raise ValueError("depends_on is only allowed on decision claims")

        now = self._now()
        today = now.date()
        observed = _parse_observed_at(f["observed_at"], today) if f["observed_at"] else today
        # Nothing can check this fact. When M2 rules fill in a default check_method,
        # they must recompute the status.
        unverifiable = kind_ is Kind.WORLD_FACT and method is CheckMethod.NONE

        return Claim(
            id=claim_id,
            text=text_,
            kind=kind_,
            subject=f["subject"],
            attribute=f["attribute"],
            value=f["value"],
            volatility=volatility,
            volatility_source=volatility_source,
            check_method=method,
            check_method_source=method_source,
            check_target=f["check_target"],
            source_url=f["source_url"],
            source_quote=f["source_quote"],
            observed_at=observed,
            recorded_at=now.astimezone(UTC).replace(microsecond=0),
            last_checked_at=None,
            next_check_at=scheduler.next_check_at(volatility, observed),
            status=Status.UNVERIFIABLE if unverifiable else Status.FRESH,
            depends_on=deps,
        )

    def _exists(self, claim_id: str) -> bool:
        row = self._conn.execute("SELECT 1 FROM claims WHERE id = ?", (claim_id,)).fetchone()
        return row is not None

    def _insert_row(self, claim: Claim) -> None:
        """Caller holds the lock and the transaction."""
        row = claim.to_dict()
        row.pop("depends_on")
        columns = ", ".join(row)
        placeholders = ", ".join(f":{c}" for c in row)
        self._conn.execute(f"INSERT INTO claims ({columns}) VALUES ({placeholders})", row)

    def _insert_depends_on(self, claim: Claim) -> None:
        """Caller holds the lock and the transaction."""
        for dep in claim.depends_on:
            if dep == claim.id:
                raise ValueError(f"claim {claim.id!r} cannot depend on itself")
            if not self._exists(dep):
                raise ValueError(f"depends_on refers to unknown claim {dep!r}")
        self._conn.executemany(
            "INSERT INTO depends_on (decision_id, claim_id) VALUES (?, ?)",
            [(claim.id, dep) for dep in claim.depends_on],
        )

    # --- reads ------------------------------------------------------------------------

    def get(self, claim_id: str) -> Claim | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
            return None if row is None else self._to_claim(row)

    def recall(self, query: str, limit: int = 10) -> list[Claim]:
        """Substring search over text and subject, best match first (D8). Skips retired claims.

        Each query word is matched on its own: words of 3 or more characters through the
        trigram index, shorter ones (common in Korean, such as "가격") with LIKE, because a
        trigram cannot match them. Claims that match more query words come first, then
        better bm25 scores, so a short common word cannot push a better match out of the
        top results. Words are always quoted, so FTS5 syntax in a query is never
        interpreted.
        """
        # Dedupe ignoring case, but keep each word's spelling: LIKE folds ASCII case only.
        words = list({w.casefold(): w for w in re.findall(r"\w+", query)}.values())
        if not words:
            return []
        hit_terms, params = [], []
        for w in words:
            if len(w) >= 3:
                hit_terms.append(
                    "c.rowid IN (SELECT rowid FROM claims_fts WHERE claims_fts MATCH ?)"
                )
                params.append(f'"{w}"')
            else:
                hit_terms.append(
                    "c.text LIKE ? ESCAPE '\\' OR coalesce(c.subject, '') LIKE ? ESCAPE '\\'"
                )
                pattern = "%" + w.replace("_", "\\_") + "%"  # \w+ holds no % or \
                params += [pattern, pattern]
        # Each term is 0 or 1; the parentheses matter because "+" binds tighter than "IN".
        hits = " + ".join(f"({t})" for t in hit_terms)

        join, score = "", "0"
        long_words = [w for w in words if len(w) >= 3]
        if long_words:
            join = """LEFT JOIN (
                    SELECT rowid, bm25(claims_fts) AS score FROM claims_fts WHERE claims_fts MATCH ?
                  ) s ON s.rowid = c.rowid"""
            score = "coalesce(s.score, 0)"  # bm25 is negative; lower is better
            params.append(" OR ".join(f'"{w}"' for w in long_words))

        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT * FROM (
                  SELECT c.*, {hits} AS hits, {score} AS score
                  FROM claims c {join}
                  WHERE c.status != 'retired'
                )
                WHERE hits > 0
                ORDER BY hits DESC, score, id
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
            return [self._to_claim(r) for r in rows]

    def due(self, days: int = 0) -> list[Claim]:
        """Checkable claims whose next_check_at is on or before today + days, soonest first.

        Claims with check_method none (unverifiable facts, decisions, preferences, notes)
        are left out: nothing can check them, so they would never leave the list.
        """
        if days < 0:
            raise ValueError("days must be 0 or more")
        try:
            cutoff = (self._now().date() + timedelta(days=days)).isoformat()
        except OverflowError:
            raise ValueError(f"days is too large (got {days})") from None
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM claims
                WHERE status != 'retired' AND check_method != 'none'
                  AND next_check_at IS NOT NULL AND next_check_at <= ?
                ORDER BY next_check_at, id
                """,
                (cutoff,),
            ).fetchall()
            return [self._to_claim(r) for r in rows]

    def _to_claim(self, row: sqlite3.Row) -> Claim:
        deps = self._conn.execute(
            "SELECT claim_id FROM depends_on WHERE decision_id = ? ORDER BY rowid", (row["id"],)
        ).fetchall()
        return Claim.from_dict(dict(row) | {"depends_on": [d["claim_id"] for d in deps]})
