# Eval data card

What is in `eval/data/`, where it came from, and the rules it follows. Labels in this folder are the maintainer's; Claude builds the files and tools around them but never writes a label (CLAUDE.md).

## Release timelines (`timelines/`, M5a)

Ground truth for the 6.1 replay: when the latest version of each project changed.

- **Projects.** `timelines/projects.toml` lists PyPI projects and GitHub repositories, each with the maintainer's volatility label (`fast`, `medium` or `slow`). Claude proposed the candidates by the rules written at the top of the file; the maintainer cut the list and labeled each project while cutting, before any data was collected (D11).
- **Collection.** `uv run python -m eval.replay.collect_timelines` on the maintainer's Mac (script version `t1`), with `GITHUB_TOKEN` set: without one, GitHub allows 60 requests an hour, fewer than the repositories' pages need. Cloud sessions cannot call the GitHub API for repositories not attached to them.
  - PyPI: `https://pypi.org/pypi/<name>/json`. One row per version that has files: the time of its first file upload, and whether all its files are yanked.
  - GitHub: `https://api.github.com/repos/<owner>/<repo>/releases`, every page; a page over the 10 MB cap (each release lists its assets) restarts the listing with half the page size, down to 10. One row per published release that is not a draft: tag, `published_at`, `created_at` and the pre-release flag. A repository with a `tag` pattern in `projects.toml` keeps only the releases whose tag matches it (`re.search`), for a repository that also releases other products (D11); the collector prints how many it left out and their tag prefixes.
  - Each file also keeps what the source called latest when it was collected (`info.version`, or `/releases/latest`), and when.
- **Format.** `timelines/pypi/<name>.jsonl` and `timelines/github/<owner>__<repo>.jsonl`: a header line (`source`, `project`, `url`, `collected_at`, `latest_at_collection`, `script`, and `tag` when the project has a pattern), then one release per line, oldest first. Times are UTC to the second.
- **"Latest" rules** (D11, `eval/replay/timelines.py`), the ones the pypi and github_release verifiers read:
  - PyPI: the highest version by PEP 440 among those uploaded by the end of the day and not yanked, leaving out pre-releases unless there is nothing else.
  - GitHub: among releases published by the end of the day and not marked pre-release, the one created last (`created_at` is the date of the release's commit, so a backport made after a newer release is usually created later too).
  - Releases whose tag is outside the project's `tag` pattern never count.
  - Repositories that patch several release lines in parallel, or whose GitHub latest is set by hand, were cut (D11): under the GitHub rule their latest keeps jumping between lines, or is not what GitHub showed.
- **Young projects.** Some projects start after the replay does: claude-agent-sdk, mcp, graphiti and hindsight in the first run (the collector's "first release ... after the replay starts" line names each). The replay creates a project's claims only after its first release: before it there is no version to claim.
- **Split** (D11): dev is 2024-01-01 to 2024-12-31, test is 2025-01-01 to 2026-09-30, by time only. Policies are tuned on dev and reported on test.
- **What the data cannot see.**
  - When a version was yanked: a yanked version never counts as latest, even before its yank.
  - Releases deleted since, and versions removed from PyPI.
  - Which GitHub release was shown as latest on a past day. GitHub marks a newly published release latest unless the publisher opts out (`make_latest`), so a release published long after its commit may have been shown as latest although the rule keeps a newer one. On a repository with a tag pattern, another product's release may have been shown as latest too; the github_release verifier, which reads no pattern, would have reported it. The collector counts those days per repository; the maintainer kept the rule for react, TypeScript and ollama, 3 to 4 days each (D11).
  - A GitHub pre-release flag changed after publishing: the stored flag is today's.
  - Versions PEP 440 cannot read: they are left out.
  - The collector's `check:` lines (`problems()`) also flag a disagreement with what the source called latest at collection, a first release after the replay starts (a young project, or a release list cut short), GitHub tags with several prefixes (a monorepo), and a latest at collection outside the tag pattern (the github_release verifier reads GitHub's latest, pattern or not).
- **Collected:** not yet. Counts per project, the collection date and any `check:` lines go here after the run.
- **License.** Version strings, dates and flags are factual metadata from the PyPI JSON API and the GitHub REST API, kept only for this evaluation. No package contents or release notes are stored.

## Smoke corpus (`smoke/`)

A tiny synthetic copy of each dataset, so every eval runs end to end in CI in seconds with no network. The projects are made up, each built for one edge case of the rules:

- `smoke-backport`: a backport, a pre-release, a release late in the UTC day, a yanked version and a version PEP 440 cannot read.
- `smoke-prerelease-only`: nothing but pre-releases, so the latest is a pre-release.
- `smoke-quiet`: no release inside the replay window.
- `smoke-org/out-of-order`: a GitHub release published after a newer one but created before it, and a pre-release; the collector flags its 2 days.
- `smoke-org/two-products`: a tag pattern (`^v\d`) with another product's releases (`mcp-v`, `vscode-ext/v`) left in the file, so the smoke run tests `latest_on()`'s own filter; GitHub's latest at collection is outside the pattern, and the collector flags it.

`tests/unit/test_timelines.py` checks the changes each one was built for. Its volatility labels are left empty, as in the real list.
