"""Command line: run the MCP server over stdio (default) or import claims from JSONL."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from shelflife.server import build_server
from shelflife.store import Store, default_db_path


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """One JSON object per line; blank lines are skipped."""
    try:
        text = path.read_text(encoding="utf-8")
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
    args = parser.parse_args(argv)

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
            except ValueError as e:
                print(f"error: {e}", file=sys.stderr)
                return 1
            print(f"imported {imported} claims, skipped {skipped} already stored")
            return 0
        build_server(store).run("stdio")
    return 0
