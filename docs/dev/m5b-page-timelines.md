# M5b proposal: web-page change timelines (not decided)

Release histories are one kind of change: they are frequent, never revert and are dated exactly. This set checks whether the replay's policy ranking holds on pages people actually remember facts from. Nothing is collected or coded yet. Every choice below is the maintainer's to make.

- **Set.** 15 to 20 pages, one tracked value each (the value a claim would state), spread over expected change rates. These are candidates only; the collector's snapshot scan decides which ones pass the checks below.
  - Expected fast: OpenAI API pricing, the Anthropic API price list, GitHub Copilot plans, Cursor pricing, ChatGPT plans, Claude plans.
  - Expected medium: Slack, Notion, Vercel, Docker, GitHub and Zoom pricing; Netflix US plans (help.netflix.com); Spotify Premium US.
  - Expected slow: the IRS standard mileage rate, the AWS exam fee page behind the M3 fixture, OpenAI's usage policies and GitHub's Terms of Service (tracked value: the effective date).
  - Expected unchanged, as controls: the Apple Developer Program fee.
- **Collection.** A script the maintainer runs on the Mac, like the release timelines, since cloud sessions cannot reach `web.archive.org`. It lists snapshots from the CDX API (`statuscode:200`, `collapse=digest`, so only snapshots whose bytes changed), fetches each as `id_` (the page without Wayback's rewriting), and reads the tracked value with a per-page pattern. Only the snapshot time, URL, digest and value are committed, never page bodies.
- **Checks before a page is kept.**
  - The value is in the archived HTML. Pages that render prices with JavaScript archive an empty shell, and the web_page verifier reads no JavaScript either.
  - The snapshots are dense enough to date a change: at most 14 days between snapshots over the window. Days to detect cannot be finer than that gap, so the median gap is reported per page.
  - Same window and split as the releases: dev 2024, test 2025-01 to 2026-09.
- **Ground truth.** The pattern proposes each change, and the maintainer confirms or rejects it. These are labels, so Claude never fills them. A change is dated to the first snapshot showing the new value. A value seen in only one snapshot between two equal ones (an A/B test or a banner) is listed for the maintainer, never dropped by code. The volatility labels are given blind, before any replay result, as for the releases.
- **What the replay must change.** D12 relies on "reverts cannot occur". Prices do revert, for example when a promotion ends. On pages, stale must mean "the stored value differs from the page's value that day", which is the same as today's rule when nothing reverts. That needs a D12 amendment before any code.
- **The check, to pre-register before any page result.** The same policies, the uniform scenario, 1 question a week and 5 seeds. Report whether per-class lies above or below the fixed-N curve, as on releases, and Kendall's tau between the two corpora's policy orders by stale claim-days. With 15 to 20 pages the intervals will be wide. This is a robustness check, not a headline.
- **Reuse for 6.2.** The same snapshots give the Wayback pairs. Changed pairs come from the two snapshots around a confirmed change. Snapshots with different digests and the same value give the layout false-alarm trap. One collection then serves both M5b items.
