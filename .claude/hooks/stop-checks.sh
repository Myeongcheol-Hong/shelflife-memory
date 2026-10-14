#!/bin/bash
# Stop hook: a session cannot end while ruff or pytest fail. Exit 2 keeps Claude
# working and shows it the output.
cd "$CLAUDE_PROJECT_DIR" || exit 2
if ! output=$( { uv run ruff check . && uv run ruff format --check . && uv run pytest -q; } 2>&1 ); then
  echo "Checks fail. Fix them before ending the session; do not skip a test or change the" >&2
  echo "maintainer's work to get past this. If a failure is not yours, say so and why." >&2
  echo "$output" | tail -c 4000 >&2
  exit 2
fi
