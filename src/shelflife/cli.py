"""Command line: run the MCP server over stdio (default), import claims from JSONL, or run
the write checks over a JSONL file."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from shelflife import writechecks
from shelflife.server import build_server
from shelflife.store import Store, default_db_path
from shelflife.verifiers import http_get
from shelflife.verifiers.web_page import fetch_page


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """One JSON object per line; blank lines are skipped. A UTF-8 byte-order mark, which
    some Windows editors write, is ignored."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as e:
        raise ValueError(f"{path}: not UTF-8 ({e.reason})") from None
    records = []
    # Split on \n only: splitlines() would also split on U+2028 and similar characters,
    # which JSON allows inside strings (a copied source_quote can contain them).
    for lineno, line in enumerate(text.split("\n"), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path}:{lineno}: not valid JSON ({e.msg})") from None
        if not isinstance(record, dict):
            raise ValueError(f"{path}:{lineno}: expected a JSON object")
        records.append(record)
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="shelflife-memory",
        description="Shelf Life MCP memory. The database is $SHELFLIFE_DB, "
        "or ~/.shelflife/shelflife.db if it is not set.",
    )
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("serve", help="run the MCP server over stdio (the default)")
    import_cmd = commands.add_parser(
        "import", help="import claims from a JSONL file; ids already stored are skipped"
    )
    import_cmd.add_argument("path", type=Path)
    check_cmd = commands.add_parser(
        "check-writes",
        help="run the four write checks (design 6.0-1) over a JSONL file of claims and "
        "print one JSON line per claim and check, then a summary; stores nothing",
    )
    check_cmd.add_argument("path", type=Path)
    args = parser.parse_args(argv)

    if args.command == "check-writes":
        try:
            records = read_jsonl(args.path)
        except (OSError, ValueError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        rows = writechecks.run(records, fetch=http_get, get_page=fetch_page)
        for row in rows:
            print(json.dumps(row, ensure_ascii=False))
        print(json.dumps({"summary": writechecks.summarize(rows)}))
        return 0

    try:
        # Read the file first, so a mistyped path does not create a database.
        records = read_jsonl(args.path) if args.command == "import" else []
        store = Store(default_db_path())
    except (OSError, ValueError, RuntimeError, sqlite3.DatabaseError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    with store:
        if args.command == "import":
            try:
                imported, skipped = store.import_claims(records)
            except (ValueError, sqlite3.DatabaseError) as e:  # "database is locked" too
                print(f"error: {e}", file=sys.stderr)
                return 1
            print(f"imported {imported} claims, skipped {skipped} already stored")
            return 0
        build_server(store).run("stdio")
    return 0
