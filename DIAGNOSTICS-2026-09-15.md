# Instagram recovery investigation, 2026-09-15

## Status: NOT RESTORED

Production main remains `6b905cdbbcc811aaab3cd125cf045a0da86cc524`.
No Slack message was sent and no delivery state was changed in this investigation.
The workstation is only a diagnostic environment, not a replacement scheduler.

## Observed results

| Environment | Result |
| --- | --- |
| PC, unchanged production Python and anonymous headless Chromium | Profile accessible; selection failed because two latest tiles had the same publication day |
| PC, targeted tile inspection | HTTP 200, six visible posts including the older pinned notice |
| GitHub Ubuntu headless, previous main diagnostic | HTTP 429, empty body |
| GitHub Windows headless, same locked Playwright | HTTP 429, empty body |
| GitHub macOS headless, same locked Playwright | HTTP 429, empty body |
| GitHub Ubuntu headed Chromium under Xvfb | Navigation failed with `net::ERR_HTTP_RESPONSE_CODE_FAILURE`; HTTP status was not captured |
| PC, corrected same-day selection, full notifier dry run | Exit 0, selected `DdQhOznzUAw`, delivery state SHA256 unchanged |

Evidence:

- [Original Ubuntu run](https://github.com/hangyeollim-conpa/kanbu_lunch/actions/runs/34934476249)
- [Windows and macOS comparison](https://github.com/hangyeollim-conpa/kanbu_lunch/actions/runs/34935922635), commit `d22eab5`
- [Headed Ubuntu comparison](https://github.com/hangyeollim-conpa/kanbu_lunch/actions/runs/34936110142), commit `4b10ca9`
- [Full Linux CI for code correction](https://github.com/hangyeollim-conpa/kanbu_lunch/actions/runs/34936110092)

The repository is public; only standard hosted runners were used. GitHub documents
[free standard runners for public repositories](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
The temporary push-triggered comparison workflow was removed after these experiments
so subsequent pushes do not make extra Instagram requests. Its exact definitions
remain available at the commits above.

## Separate selection defect and correction

The image descriptions for both `DdQhOznzUAw` and `DdOfeu7O0oj` said
`September 13, 2026`. Their own permalink-linked HTML time elements reported:

- `DdQhOznzUAw`: `2026-09-14T06:43:24.000Z` (15:43:24 KST).
- `DdOfeu7O0oj`: `2026-09-13T11:49:38.000Z`.

A different, non-permalink time element on the second page differed by one second.
The correction therefore uses only time elements under the candidate's own post
permalink, not arbitrary time elements that can refer to comments.

When the latest publication day is tied, the browser opens each tied candidate
once and compares its exact publication time. Missing, invalid, conflicting,
login-required, or denied detail pages still fail; tile order and menu text are
never used to guess. Existing day-based selection remains for a unique latest day.
This adds requests only for same-day ambiguity and does not fix cloud access.

Local related checks: 45 passed; Ruff passed; basedpyright reported zero errors.
The successful local command was:

```powershell
uv run --locked --no-dev --with tzdata python instagram_slack_notifier.py --config config.example.json --dry-run
```

Windows required temporary `tzdata` because it has no system IANA timezone database.
No dependency or lockfile change was made for this diagnostic accommodation.
The example config has no usable Slack credential. The real secret was never read.

## What the evidence establishes

The same anonymous headless approach can access this profile on the workstation.
Changing GitHub's operating system to Windows or macOS did not restore access in
the tested runs. Headed mode also failed in its tested run. The results implicate
environment-dependent access restrictions, but do not isolate IP reputation from
network, geographic, fingerprint, or combined request-policy effects.

**RED FLAG:** Local success and mocked CI success are not successful production
Instagram access. This branch must not be presented as an operational recovery.
No production runner, scheduler, webhook, or state configuration has been changed.
The remaining requirement is a verified anonymous cloud retrieval path under the
original free, PC-off, no-server constraints. Repeating the same failed requests
or merging only the selector correction cannot establish that requirement.
