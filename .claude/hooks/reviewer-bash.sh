#!/bin/bash
# PreToolUse hook of the pr-reviewer agent: its Bash may only run the tests, with -q, -x,
# -v, -k NAME and paths under tests/. Anything else is blocked, including pytest options
# that write or delete files (--basetemp, --junitxml) and input that cannot be read.
command=$(python3 -I -c 'import json, sys; print(json.load(sys.stdin)["tool_input"]["command"])')
allowed='^uv run pytest( (-[qxv]|-k [A-Za-z0-9_]+|tests(/[][A-Za-z0-9_./:=,+-]*)?))*$'
if [[ $command =~ $allowed && $command != *..* ]]; then
  exit 0
fi
echo "pr-reviewer may only run: uv run pytest [-q] [-x] [-v] [-k NAME] [tests/...]" >&2
exit 2
