# Verifier fixtures

Responses the verifier tests read instead of the live network. `record.py` re-records them and trims each response to a few fields: the one the verifier reads (`info.version`, `tag_name`) plus `name` and, for GitHub, `html_url`, `published_at`, `draft` and `prerelease`, so the files stay small and the test that the verifier ignores a release's `name` has data.

| Files | Source |
|---|---|
| `pypi/*.json` | Recorded from `https://pypi.org/pypi/<name>/json` on 2026-10-13 |
| `pages/*.html` | The seed `web_page` claims' pages, recorded on 2026-10-13 through `fetch_page` and re-encoded as UTF-8. To keep them small, `record.py` drops comments, SVG and every attribute the extractor does not read (it keeps `hidden`, `aria-hidden`, a hiding `style`, and `<meta>` charset fields), and drops scripts and styles except on `aws-aip-c01`, so one fixture tests on real input that script text is never extracted. It refuses to save a page whose slimmed form extracts to different text. `pages/index.json` keeps each page's URL, final URL, status, content type, charset, size and the SHA-256 of the original body |
| `github/*.json` | Written by hand on 2026-10-13 in the documented shape of `GET /repos/{owner}/{repo}/releases/latest`, because the cloud session that wrote them could not reach the GitHub API (HTTP 403). The same day the owner checked them against the live API: `tag_name`, `html_url`, `draft` and `prerelease` matched, and the owner supplied `name` and `published_at`. `record.py` re-records them where the API is reachable. |
