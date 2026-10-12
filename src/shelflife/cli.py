"""Command line: run the MCP server over stdio (default) or import claims from JSONL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from shelflife.server import build_server
from shelflife.store import Store, default_db_path


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """One JSON object per line; blank lines are skipped."""
    records = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
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

    with Store(default_db_path()) as store:
        if args.command == "import":
            try:
                imported, skipped = store.import_claims(read_jsonl(args.path))
            except (OSError, ValueError) as e:
                print(f"error: {e}", file=sys.stderr)
                return 1
            print(f"imported {imported} claims, skipped {skipped} already stored")
            return 0
        build_server(store).run("stdio")
    return 0
