#!/bin/bash
# Stop hook: a session cannot end while ruff or pytest fail. Exit 2 keeps Claude
# working and shows it the output.
cd "$CLAUDE_PROJECT_DIR" || exit 2
if ! output=$( { uv run ruff check . && uv run ruff format --check . && uv run pytest -q; } 2>&1 ); then
  echo "Checks fail; fix them before ending the session:" >&2
  echo "$output" | tail -n 40 >&2
  exit 2
fi
