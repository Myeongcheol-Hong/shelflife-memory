"""A stand-in for `claude` in tests/unit/test_runner.py. It prints, in the shape of
`claude -p --output-format json`, what the runner sent it: its arguments, its folder,
its stdin and which watched environment variables reached it. FAKE_CLAUDE picks a
failure, shaped as the real ones are."""

import json
import os
import sys
import time

args = sys.argv[1:]
if args == ["--version"]:
    print("9.9.9 (Claude Code)")
    sys.exit(0)
mode = os.environ.get("FAKE_CLAUDE", "ok")
model = args[args.index("--model") + 1]
stdin = sys.stdin.read()
watched = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_EFFORT", "MAX_THINKING_TOKENS")
watched += ("CLAUDE_CODE_MAX_OUTPUT_TOKENS", "KEEP_ME")
env = sorted(k for k in watched if k in os.environ)
if mode == "sleep":
    time.sleep(10)
if mode == "garbage":
    print("not json")
    print("boom", file=sys.stderr)
    sys.exit(2)
reply = {
    "type": "result",
    "subtype": "success",
    "is_error": False,
    "result": json.dumps({"args": args, "cwd": os.getcwd(), "stdin": stdin, "env": env}),
    "total_cost_usd": 0.001,
    "duration_ms": 5,
    "modelUsage": {model: {}},
}
if mode == "error":  # what `claude -p` prints for an unknown model, and exits 1
    reply |= {"is_error": True, "result": "There's an issue with the selected model."}
    reply["modelUsage"] = {}
if mode == "other":
    reply["modelUsage"] = {"claude-other-0": {}}
print(json.dumps(reply))
sys.exit(1 if mode == "error" else 0)
