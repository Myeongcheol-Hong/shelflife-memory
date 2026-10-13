# Verifier fixtures

Responses the verifier tests read instead of the live network. `record.py` re-records them and trims each response to the fields the verifiers read.

| Files | Source |
|---|---|
| `pypi/*.json` | Recorded from `https://pypi.org/pypi/<name>/json` on 2026-10-13 |
| `github/*.json` | Written by hand on 2026-10-13 in the documented shape of `GET /repos/{owner}/{repo}/releases/latest`, because the cloud session that wrote them could not reach the GitHub API (HTTP 403). The tags come from `examples/seed_claims.jsonl`. Run `record.py` where the API is reachable to replace them with recorded responses. |
