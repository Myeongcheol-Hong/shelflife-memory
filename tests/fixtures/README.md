# Verifier fixtures

Responses the verifier tests read instead of the live network. `record.py` re-records them and trims each response to a few fields: the one the verifier reads (`info.version`, `tag_name`) plus `name` and, for GitHub, `html_url`, `published_at`, `draft` and `prerelease`, so the files stay small and the test that the verifier ignores a release's `name` has data.

| Files | Source |
|---|---|
| `pypi/*.json` | Recorded from `https://pypi.org/pypi/<name>/json` on 2026-10-13 |
| `github/*.json` | Written by hand on 2026-10-13 in the documented shape of `GET /repos/{owner}/{repo}/releases/latest`, because the cloud session that wrote them could not reach the GitHub API (HTTP 403). The same day the owner checked them against the live API: `tag_name`, `html_url`, `draft` and `prerelease` matched, and the owner supplied `name` and `published_at`. `record.py` re-records them where the API is reachable. |
