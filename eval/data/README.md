# Eval data card

What is in `eval/data/`, where it came from, and the rules it follows. Labels in this folder are the maintainer's; Claude builds the files and tools around them but never writes a label (CLAUDE.md).

## Release timelines (`timelines/`, M5a)

Ground truth for the 6.1 replay: when the latest version of each project changed.

- **Projects.** `timelines/projects.toml` lists PyPI projects and GitHub repositories, each with the maintainer's volatility label (`fast`, `medium` or `slow`). Claude proposed the candidates by the rules written at the top of the file; the maintainer cut the list and labeled each project while cutting, before any data was collected (D11).
- **Collection.** `uv run python -m eval.replay.collect_timelines` on the maintainer's Mac (script version `t1`). Cloud sessions cannot call the GitHub API for repositories not attached to them.
  - PyPI: `https://pypi.org/pypi/<name>/json`. One row per version that has files: the time of its first file upload, and whether all its files are yanked.
  - GitHub: `https://api.github.com/repos/<owner>/<repo>/releases`, every page, with `GITHUB_TOKEN` if set. One row per published release that is not a draft: tag, `published_at`, `created_at` and the pre-release flag.
  - Each file also keeps what the source called latest when it was collected (`info.version`, or `/releases/latest`), and when.
- **Format.** `timelines/pypi/<name>.jsonl` and `timelines/github/<owner>__<repo>.jsonl`: a header line (`source`, `project`, `url`, `collected_at`, `latest_at_collection`, `script`), then one release per line, oldest first. Times are UTC to the second.
- **"Latest" rules** (D11, `eval/replay/timelines.py`), the ones the pypi and github_release verifiers read:
  - PyPI: the highest version by PEP 440 among those uploaded by the end of the day and not yanked, leaving out pre-releases unless there is nothing else.
  - GitHub: among releases published by the end of the day and not marked pre-release, the one created last.
- **Split** (D11): dev is 2024-01-01 to 2024-12-31, test is 2025-01-01 to 2026-09-30, by time only. Policies are tuned on dev and reported on test.
- **What the data cannot see.**
  - When a version was yanked: a yanked version never counts as latest, even before its yank.
  - Releases deleted since, and versions removed from PyPI.
  - A GitHub release marked latest by hand, against the created-last rule.
  - Versions PEP 440 cannot read: they are left out.
  - The collector's `check:` lines and `problems()` flag the last two when they change what the source called latest at collection, and GitHub tags with several prefixes (a monorepo).
- **Collected:** not yet. Counts per project, the collection date and any `check:` lines go here after the run.
- **License.** Version strings, dates and flags are factual metadata from the PyPI JSON API and the GitHub REST API, kept only for this evaluation. No package contents or release notes are stored.

## Smoke corpus (`smoke/`)

A tiny synthetic copy of each dataset, so every eval runs end to end in CI in seconds with no network. The projects are made up, each built for one edge case of the rules:

- `smoke-backport`: a backport, a pre-release, a release late in the UTC day, a yanked version and a version PEP 440 cannot read.
- `smoke-prerelease-only`: nothing but pre-releases, so the latest is a pre-release.
- `smoke-quiet`: no release inside the replay window.
- `smoke-org/out-of-order`: a GitHub release published after a newer one but created before it, and a pre-release.

`tests/unit/test_timelines.py` checks the changes each one was built for. Its volatility labels are left empty, as in the real list.
