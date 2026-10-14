import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from shelflife import store as store_module
from shelflife.cli import main, read_jsonl
from shelflife.models import FieldSource, Status

SEED = Path(__file__).parents[2] / "examples" / "seed_claims.jsonl"


def test_seed_file_imports_once(store):
    records = read_jsonl(SEED)
    assert store.import_claims(records) == (len(records), 0)
    assert store.import_claims(records) == (0, len(records))

    pypi = store.get("seed-pypi-mcp")
    assert pypi.status is Status.FRESH
    assert pypi.volatility_source is FieldSource.CALLER
    assert pypi.next_check_at == date(2026, 10, 19)  # observed 2026-10-12, fast

    assert store.get("seed-ai-102-retired").status is Status.UNVERIFIABLE
    assert store.get("seed-decision-focus").depends_on == ("seed-memguard-no-eval",)


def test_reimport_adds_only_new_ids(store):
    a = {"id": "a", "text": "First note", "kind": "note"}
    b = {"id": "b", "text": "Second note", "kind": "note"}
    assert store.import_claims([a]) == (1, 0)
    assert store.import_claims([a, b]) == (1, 1)
    assert store.get("b") is not None


def test_dependencies_may_come_later_in_the_file(store):
    records = [
        {"id": "d", "text": "Pick X", "kind": "decision", "depends_on": ["f"]},
        {"id": "f", "text": "X is cheap", "kind": "world_fact"},
    ]
    assert store.import_claims(records) == (2, 0)
    assert store.get("d").depends_on == ("f",)


@pytest.mark.parametrize(
    ("record", "message"),
    [
        ({"text": "No id", "kind": "note"}, r"record 2: id is required"),
        ({"id": 7, "text": "Number id", "kind": "note"}, r"record 2: id must be a string"),
        ({"id": "x", "text": "Bad", "kind": "note", "status": "fresh"}, "system-managed"),
        ({"id": "x", "text": "Bad", "kind": "fact"}, r"record 2 \(x\): kind must be one of"),
        ({"id": "x", "text": "Self", "kind": "decision", "depends_on": ["x"]}, "itself"),
        ({"id": "x", "text": "Gone", "kind": "decision", "depends_on": ["y"]}, "unknown claim"),
        ({"id": "ok", "text": "Twice", "kind": "note"}, "duplicate id 'ok'"),
    ],
)
def test_one_bad_record_stores_nothing(store, record, message):
    good = {"id": "ok", "text": "A good note", "kind": "note"}
    with pytest.raises(ValueError, match=message):
        store.import_claims([good, record])
    assert store.get("ok") is None


def test_cli_import(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SHELFLIFE_DB", str(tmp_path / "cli.db"))
    path = tmp_path / "claims.jsonl"
    path.write_text(json.dumps({"id": "n1", "text": "A note", "kind": "note"}) + "\n\n")

    assert main(["import", str(path)]) == 0
    assert main(["import", str(path)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "imported 1 claims, skipped 0 already stored",
        "imported 0 claims, skipped 1 already stored",
    ]

    path.write_text("{not json\n")
    assert main(["import", str(path)]) == 1
    assert "claims.jsonl:1: not valid JSON" in capsys.readouterr().err

    path.write_bytes(b"\xff\xfe")
    assert main(["import", str(path)]) == 1
    assert "claims.jsonl: not UTF-8" in capsys.readouterr().err


def test_a_byte_order_mark_is_ignored(tmp_path):
    record = {"id": "n1", "text": "A note", "kind": "note"}
    path = tmp_path / "claims.jsonl"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8-sig")  # as Notepad saves
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert read_jsonl(path) == [record]


def test_a_locked_database_is_an_error_line_not_a_traceback(tmp_path, monkeypatch, capsys):
    db = tmp_path / "cli.db"
    monkeypatch.setenv("SHELFLIFE_DB", str(db))
    monkeypatch.setattr(store_module, "BUSY_TIMEOUT_SECONDS", 0.1)
    path = tmp_path / "claims.jsonl"
    path.write_text(json.dumps({"id": "n1", "text": "A note", "kind": "note"}) + "\n")
    store_module.Store(db).close()
    other = sqlite3.connect(db)
    other.execute("BEGIN IMMEDIATE")  # another server process is writing
    try:
        assert main(["import", str(path)]) == 1
    finally:
        other.rollback()
        other.close()
    assert capsys.readouterr().err == "error: database is locked\n"


def test_cli_import_of_a_missing_file_creates_no_database(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SHELFLIFE_DB", str(tmp_path / "new" / "cli.db"))
    assert main(["import", str(tmp_path / "missing.jsonl")]) == 1
    assert "missing.jsonl" in capsys.readouterr().err
    assert not (tmp_path / "new").exists()


def test_jsonl_lines_split_on_newline_only(tmp_path):
    record = {"id": "q", "text": "Fee", "kind": "note", "value": "a\u2028b\u0085c"}
    path = tmp_path / "claims.jsonl"
    path.write_text(json.dumps(record, ensure_ascii=False) + "\r\n", encoding="utf-8")
    assert read_jsonl(path) == [record]
