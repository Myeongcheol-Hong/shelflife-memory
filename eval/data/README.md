# Eval data card

What is in `eval/data/`, where it came from, and the rules it follows. Labels in this folder are the maintainer's; Claude builds the files and tools around them but never writes a label (CLAUDE.md).

## Release timelines (`timelines/`, M5a)

Ground truth for the 6.1 replay: when the latest version of each project changed.

- **Projects.** `timelines/projects.toml` lists PyPI projects and GitHub repositories, each with the maintainer's volatility label (`fast`, `medium` or `slow`). Claude proposed the candidates by the rules written at the top of the file; the maintainer cut the list and labeled each project while cutting, before any data was collected (D11); the four GitHub repositories added after the first collection run were labeled after it.
- **Collection.** `uv run python -m eval.replay.collect_timelines` on the maintainer's Mac (script version `t1`; `t2` reads a release that shows up on two pages once), with `GITHUB_TOKEN` set: without one, GitHub allows 60 requests an hour, fewer than the repositories' pages need. Cloud sessions cannot call the GitHub API for repositories not attached to them.
  - PyPI: `https://pypi.org/pypi/<name>/json`. One row per version that has files: the time of its first file upload, and whether all its files are yanked. A version without files is not collected: it was never installable.
  - GitHub: `https://api.github.com/repos/<owner>/<repo>/releases`, every page; a page over the 10 MB cap (each release lists its assets) restarts the listing with half the page size, down to 10. One row per published release that is not a draft, read once even when it shows up on two pages (by release id): tag, `published_at`, `created_at` and the pre-release flag. A repository with a `tag` pattern in `projects.toml` keeps only the releases whose tag matches it (`re.search`), for a repository that also releases other products (D11); the collector prints how many it left out and their tag prefixes.
  - Each file also keeps what the source called latest when it was collected (`info.version`, or `/releases/latest`), and when.
- **Format.** `timelines/pypi/<name>.jsonl` and `timelines/github/<owner>__<repo>.jsonl`: a header line (`source`, `project`, `url`, `collected_at`, `latest_at_collection`, `script`, and `tag` when the project has a pattern), then one release per line, oldest first. Times are UTC to the second.
- **"Latest" rules** (D11, `eval/replay/timelines.py`), the ones the pypi and github_release verifiers read:
  - PyPI: the highest version by PEP 440 among those uploaded by the end of the day and not yanked, leaving out pre-releases unless there is nothing else.
  - GitHub: among releases published by the end of the day and not marked pre-release, the one created last. `created_at` is GitHub's value at collection: GitHub documents it as the date of the commit the release's tag points to, so it moves when the tag is moved after publishing (jq's first releases show their 2012-2014 commits but were published in 2015): 140 collected rows had it later than `published_at` (ollama 132, since cut; jq 3, TypeScript 2, terraform, prettier and zed 1 each). The rule therefore reads min(`created_at`, `published_at`), so no past day is decided by a timestamp from after it; on the 70 kept projects this changes no day's latest. The collector's comparison with the source's latest at collection reads the stored `created_at`, as GitHub did then.
  - Releases whose tag is outside the project's `tag` pattern never count.
  - Repositories that patch several release lines in parallel (react among them), whose GitHub latest is set by hand, or whose `created_at` moved too often to rebuild their past (ollama) were cut (D11).
- **Young projects.** Four projects start after the replay does: claude-agent-sdk, mcp, graphiti and hindsight (the collector's "first release ... after the replay starts" line names each). The replay creates a project's claims only after its first release: before it there is no version to claim. `changes()` counts that first release as a change (from no version to the first), so the change counts below include it for these four.
- **Split** (D11): dev is 2024-01-01 to 2024-12-31, test is 2025-01-01 to 2026-09-30, by time only. Policies are tuned on dev and reported on test.
- **What the data cannot see.**
  - When a version was yanked: a yanked version never counts as latest, even before its yank.
  - Releases deleted since, and versions removed from PyPI.
  - Which GitHub release was shown as latest on a past day. GitHub marks a newly published release latest unless the publisher opts out (`make_latest`), so a release published long after its commit may have been shown as latest although the rule keeps a newer one. On a repository with a tag pattern, another product's release may have been shown as latest too; the github_release verifier, which reads no pattern, would have reported it. The collector counts those days per repository; the maintainer kept the rule for TypeScript (3 days) and hugo (1) (D11).
  - The pre-release flag and `created_at` are today's values, not the values on a past day: a release promoted from pre-release later, or a tag moved after publishing, looks as if it had always been so.
  - Versions PEP 440 cannot read: they are left out.
  - The collector's `check:` lines (`problems()`) also flag a disagreement with what the source called latest at collection, a first release after the replay starts (a young project, or a release list cut short), GitHub tags with several prefixes (a monorepo), a tag listed more than once, and a latest at collection outside the tag pattern (the github_release verifier reads GitHub's latest, pattern or not).
- **Collected** on 2026-10-14, 15:34 to 15:36 UTC, on the maintainer's Mac (script `t1`, the second run; the first one's files were deleted). Every listed project has its file. ollama and react were cut after collection (D11) and their files deleted; the numbers below are for the 70 kept projects, recounted with the rules as they are now.
  - 52 PyPI projects with 12,141 versions, and 18 GitHub repositories with 6,072 releases after the tag patterns. Each file's release count is its line count minus the header.
  - The latest changed 1,560 times in dev (PyPI 1,129, GitHub 431) and 2,929 times in test (PyPI 2,059, GitHub 870), counting the first release of mcp and graphiti (dev) and of claude-agent-sdk and hindsight (test). Per project, over both splits, from once (python-dateutil, six) to 657 times (boto3).
  - No change in dev: jq, bat, hindsight and claude-agent-sdk (the last two start later). No change in test: httpx, python-dateutil and six.
  - `check:` lines: a first release after 2024-01-01 for claude-agent-sdk, mcp, graphiti and hindsight; disputed days for TypeScript (3) and hugo (1), where the rule stays (D11); `1.66.1` listed twice by rust, in two identical rows (GitHub itself lists it twice). No project's latest disagreed with what the source called latest at collection, and none had an error.
  - The tag patterns left out only the releases expected (the collector's "left out" lines): graphiti's `mcp-`, TypeScript's `vscode-typescript/` and home-assistant's last-python release.
- **License.** Version strings, dates and flags are factual metadata from the PyPI JSON API and the GitHub REST API, kept only for this evaluation. No package contents or release notes are stored.

## Smoke corpus (`smoke/`)

A tiny synthetic copy of each dataset, so every eval runs end to end in CI in seconds with no network. The projects are made up, each built for one edge case of the rules:

- `smoke-backport`: a backport, a pre-release, a release late in the UTC day, a yanked version and a version PEP 440 cannot read.
- `smoke-prerelease-only`: nothing but pre-releases, so the latest is a pre-release.
- `smoke-quiet`: no release inside the replay window.
- `smoke-org/moved-tag`: a GitHub release whose `created_at` is later than its publish (a moved tag); the rule reads its publish time, while the comparison with the source's latest at collection reads the stored `created_at`.
- `smoke-org/out-of-order`: a GitHub release published after a newer one but created before it, and a pre-release; the collector flags its 2 days.
- `smoke-org/two-products`: a tag pattern (`^v\d`) with another product's releases (`mcp-v`, `vscode-ext/v`) left in the file, so the smoke run tests `latest_on()`'s own filter; GitHub's latest at collection is outside the pattern, and the collector flags it.

`tests/unit/test_timelines.py` checks the changes each one was built for. Its volatility labels are left empty, as in the real list.
