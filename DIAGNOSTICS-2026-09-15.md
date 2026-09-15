# Instagram recovery investigation, 2026-09-15

## Status: cloud retrieval verified; scheduled Slack delivery pending

Investigation started from main `6b905cdbbcc811aaab3cd125cf045a0da86cc524`.
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

### Initial conclusion before Apify testing

**RED FLAG:** Local success and mocked CI success are not successful production
Instagram access. This branch must not be presented as an operational recovery.
No production runner, scheduler, webhook, or state configuration has been changed.
The remaining requirement is a verified anonymous cloud retrieval path under the
original free, PC-off, no-server constraints. Repeating the same failed requests
or merging only the selector correction cannot establish that requirement.

## Apify cloud recovery

The user created an Apify Free account. Its existing token was saved as the repository
secret `APIFY_TOKEN` without printing it. No paid plan, payment method, Instagram
credentials, or restaurant authorization was introduced.

- Direct GitHub urllib profile retrieval also returned 429. The public embed was 200
  but had no usable posts. An HTTP 200 alone was rejected as recovery evidence.
- Picuki's public viewer returned real matching posts and an image on the PC, but
  GitHub Ubuntu and Windows returned HTTP 422; Windows explicitly reported
  `CAPTCHA_REQUIRED` ([run](https://github.com/hangyeollim-conpa/kanbu_lunch/actions/runs/34937805318)).
  This candidate was rejected, and its temporary parser was removed.
- Apify's official Instagram Scraper returned six posts from GitHub twice. The first
  comparison failed because a new post was published during investigation, not because
  access failed ([run](https://github.com/hangyeollim-conpa/kanbu_lunch/actions/runs/34938651445)).
- PC direct anonymous Instagram inspection independently confirmed new shortcode
  `DdTGcFvz696`, exact timestamp `1789454821` (2026-09-15 15:47:01 KST), and the
  September 16 menu. Both Apify runs selected the same ID/time. The latest image date
  is menu content, not used as the publication timestamp.
- The returned image host `instagram.fcps4-2.fna.fbcdn.net` resolved only to IPv6 on
  GitHub, which failed with `Network is unreachable`. PC DNS also could not resolve
  a usable address. This is a separate image-routing defect, not the original 429.
- Preserving the exact image path and signed query on `scontent.cdninstagram.com`
  returned the correct image on PC and GitHub. This explicit CDN normalization does
  not choose another post or guessed image. No fallback to an old dataset is used
  in production; existing dataset reads were confined to this diagnosis.
- [Verified GitHub image run](https://github.com/hangyeollim-conpa/kanbu_lunch/actions/runs/34939020132):
  `LATEST DdTGcFvz696 1789454821`, HTTP 200 `image/jpeg`, 80,428 bytes,
  SHA256 `055bd5be796004442f134a9c46eb59a732b0f823baff934c2e478e481a60974d`.
  State remained unchanged; this workflow had no Slack secret.

Apify Console showed both runs succeeded, six results each, usage rounded to $0.02
per run, with a $5 Free allowance. Requests cap usage at $0.04 and execution at 120
seconds. The current $0.0027/result price and 12-result limit fit four daily checks
within $5/month. No automatic retry, restart, paid upgrade, or alternate scraper is used.

The runtime now validates owner, ID/permalink, timestamp, and trusted image origin,
selects the unique newest timestamp, and retains existing schedule/deduplication.
A different ID with an older or ambiguous timestamp is rejected before Slack/state.
The operating workflow receives `APIFY_TOKEN` only in its run step and no longer
installs Chromium. Browser code remains for diagnostic comparisons.

Actual Slack acceptance and rendering have not been tested: the user prohibited
an unsolicited test message. The next authorized scheduled run must provide that
last piece of delivery evidence; no outside-window send was made to manufacture it.
