#!/bin/bash
# PreToolUse hook of the pr-reviewer agent: its Bash may only run the tests.
# Allows `uv run pytest` with plain arguments (no quotes or shell operators) and blocks
# anything else, including when the input cannot be read.
command=$(python3 -c 'import json, sys; print(json.load(sys.stdin)["tool_input"]["command"])') || exit 2
allowed='^uv run pytest( [][A-Za-z0-9_./:=,+ -]*)?$'
if [[ $command =~ $allowed ]]; then
  exit 0
fi
echo "pr-reviewer may only run the tests: uv run pytest [paths or options, no quotes]" >&2
exit 2
