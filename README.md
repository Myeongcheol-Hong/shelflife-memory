# Shelf Life

**Memory with an expiry date.** Shelf Life is a small MCP memory server for Claude Desktop and Claude Code. It remembers facts together with where they came from and how fast they go stale, tells you which ones are due for a check, and re-checks them against the source when you ask, so a fact that has changed is marked instead of repeated.

## The problem

Memory systems for AI assistants change a memory when new information arrives that contradicts it, or let it expire on a date set when it was stored. When the world changes and nobody mentions it, the old fact keeps being served: last month's price, last year's latest version, a policy that has since been rewritten. Nothing in the pipeline notices, so you get a confident answer that is no longer true.

## What Shelf Life does

- **Every memory carries its shelf life.** A claim stores its source, the date it was observed, a volatility class (fast, medium, slow or none) and how to check it: the PyPI project, the GitHub repository, or the web page it came from.
- **Claims can be re-checked when they are due.** `due` lists the claims past their check date, and `verify` re-checks one; nothing is re-checked automatically yet (a daily run is on the roadmap, M4). Version claims are compared with PyPI and GitHub releases by code. For a web page, the server fetches the page and picks out the relevant section; Claude judges it in the conversation, and a `same` or `changed` judgment is stored only if its quote appears word for word on the page. A changed claim keeps its old value and is marked `changed`, so you decide what happens next.
- **Decisions remember their grounds.** A decision can point to the claims it rests on. Flagging the decision for review when one of them changes is on the roadmap (M4).
- **It is light.** One SQLite file on your machine, no Docker, no services, no API keys. Search works in English and Korean.

The project's main contribution is an evaluation, still in progress: replaying real release histories to measure *when* re-checking pays off (fewer stale answers for the same number of checks), and measuring how accurate the write and verify steps are. See [`docs/design.md`](docs/design.md).

## Quick start (from source)

You need [uv](https://docs.astral.sh/uv/) and Python 3.11 or later.

```sh
git clone https://github.com/Myeongcheol-Hong/shelflife-memory.git
cd shelflife-memory
uv sync
claude mcp add -s user shelflife -- uv run --directory "$PWD" shelflife-memory
```

The last line registers the server with Claude Code for all your projects; replace `"$PWD"` with the clone's path if you run it from elsewhere.

For Claude Desktop, add the server to `claude_desktop_config.json` (Settings, Developer, Edit Config; on macOS it is in `~/Library/Application Support/Claude/`, on Windows in `%APPDATA%\Claude\`) and restart the app:

```json
{
  "mcpServers": {
    "shelflife": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/shelflife-memory", "shelflife-memory"]
    }
  }
}
```

Use the clone's full path. If Claude Desktop cannot find `uv`, put the full path that `which uv` prints in `command`. Both apps can use the server at once and share one database.

The database lives at `~/.shelflife/shelflife.db`, or wherever `SHELFLIFE_DB` points. When Shelf Life creates the file, only your user can read it (mode 0600, and 0700 for a folder it creates); a file or folder that already exists keeps its mode.

## Tools

| Tool | What it does |
|---|---|
| `remember` | Stores a claim: the sentence, its kind (world fact, decision, preference or note), and optionally its value, source, volatility and check method. For a world fact, rules fill in what is left empty where they can. |
| `recall` | Searches stored claims by key words. |
| `due` | Lists the claims due for a check, the ones a check found changed, and the facts that nothing can check yet. |
| `verify` | Re-checks one claim now. Version claims are compared with PyPI or GitHub; for a web page it returns the page section and a prompt for Claude to judge. |
| `record_check` | Stores Claude's judgment of a web page, after code confirms the quote is on the page. |
| `forget` | Retires a claim: `recall` and `due` no longer show it, and nothing is deleted. |

## Status

Early and in active development. The store, the six tools, the PyPI, GitHub and web page checks, and the write checks are done (milestones M1-M3). Next come the evaluation data and the re-check policy replay; the scheduler, weekly digest and decision review follow. See [`docs/roadmap.md`](docs/roadmap.md).

## Prior art

Memory systems such as [Hindsight](https://github.com/vectorize-io/hindsight) and Zep ([Graphiti](https://github.com/getzep/graphiti)) update a memory when contradicting information arrives, or leave invalidation to you. [Mem0](https://github.com/mem0ai/mem0) only adds memories; a memory can carry an expiration date, after which it is hidden. A few tools are built on top of them to catch the changes nobody mentions:

- [MemGuard](https://github.com/ac12644/MemGuard) re-fetches source URLs for Mem0, Zep and other memory stores, with trust scores and quarantine. It is the closest match to Shelf Life.
- [agent-memory-staleness-audit](https://github.com/a-bhimava/agent-memory-staleness-audit) scores staleness from provenance and per-type half-lives, without going back to the source.

Shelf Life's evaluation is meant to add what they leave open: a reproducible measurement of when to re-check, and the verifier's accuracy on labeled page snapshots. It also links decisions to their grounds, in a single-file tool for personal use. [`docs/design.md`](docs/design.md) section 1 compares them in more detail.

## License

MIT
