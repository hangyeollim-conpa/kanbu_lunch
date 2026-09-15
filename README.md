# Instagram to Slack Notifier

This repository checks the public Instagram profile `@lunch11_14` and sends its latest post image to Slack during the 10:30-11:00 Asia/Seoul window. It checks again when no new post is found and stops automatic notifications after a successful delivery that day.

## Instagram access

The notifier uses Apify's official `apify/instagram-scraper` to read this public profile from the cloud. It requires an Apify Free account and the GitHub Actions secret `APIFY_TOKEN`, in addition to `SLACK_WEBHOOK_URL`. No Instagram login, account ownership, Facebook page, always-on PC, or private server is needed.

Each check requests up to 12 posts and selects the unique newest exact publication timestamp, ignoring pinned order. Missing data, another account, conflicting timestamps, and invalid image URLs fail explicitly. It never switches to an old cached dataset or another scraper after failure.

The returned regional image CDN may be IPv6-only. The adapter uses `scontent.cdninstagram.com` while preserving the exact signed image path and query. This is CDN host normalization, not substitution of a different post or image. The browser and legacy API readers remain only for diagnosis and regression tests.

### Free limits

The [Apify Free plan](https://apify.com/pricing) includes $5 of monthly usage without a card. Each run has a hard `$0.04` usage cap and 120-second timeout, with no automatic restart. At the verified Free price of $0.0027 per post, 12 results cost at most $0.0324; four checks per day for 31 days cost about $4.02. Successful daily delivery suppresses later checks, reducing actual usage. Other Apify tasks and manual dry-runs share the same free credits. Keep the account on Free; exhaustion blocks service until credits renew instead of requiring a paid upgrade.

### Recovery evidence

See [the investigation report](DIAGNOSTICS-2026-09-15.md) for local, hosted, image, and delivery evidence separately. A successful CI or outside-window skip does not establish delivery. No Slack test message was authorized during this repair.

## Files

- `instagram_slack_notifier.py`: main checker script
- `instagram_apify.py`: bounded cloud retrieval and exact-time selection
- `instagram_browser.py`: diagnostic anonymous browser reader
- `instagram_public.py`: typed public tile parsing and latest-date selection
- `instagram_client.py`: shared post model and legacy API client
- `config.example.json`: optional local test config template
- `.github/workflows/instagram-slack-notifier.yml`: daily GitHub Actions workflow
- `.github/workflows/tests.yml`: isolated regression tests on Python 3.12–3.14

## Trigger setup

1. Open the repository on GitHub
2. Go to `Settings` -> `Secrets and variables` -> `Actions`
3. Add a new repository secret named `SLACK_WEBHOOK_URL`
4. Paste your Slack Incoming Webhook URL
5. Add `APIFY_TOKEN` from your Apify Free account as another repository secret.
6. Create a GitHub fine-grained personal access token for this repository with `Contents: Write`
7. In `cron-job.org`, create a daily job that sends a `POST` request to:

```text
https://api.github.com/repos/hangyeollim-conpa/kanbu_lunch/dispatches
```

8. Use these headers in `cron-job.org`:

```text
Accept: application/vnd.github+json
Authorization: Bearer YOUR_GITHUB_TOKEN
Content-Type: application/json
X-GitHub-Api-Version: 2026-03-10
```

9. Use this JSON request body:

```json
{"event_type":"instagram-slack-notifier"}
```

## Schedule

- The workflow also has a GitHub Actions fallback schedule at `10:38`, `10:46`, and `10:54` KST
- `cron-job.org` can call the same workflow during the `10:30-11:00` window in `Asia/Seoul`
- The existing external job runs around 10:43 KST on weekdays; retain that configuration.
- The script checks the automatic time window before contacting Instagram and again after retrieval. Runs outside the window log a skip; an Actions success alone does not prove delivery.
- A check with no new post leaves the state unchanged, allowing a later check to catch a new menu.
- Once a successful automatic delivery is saved for the day, further automatic runs skip without contacting Instagram.
- You can also run it manually from the `Actions` tab with `Run workflow`
- Manual runs default to `dry_run`: inspect the latest post without Slack delivery or state changes. To send a manual test, disable `dry_run` and enable `force_notify`.
- All workflow triggers share one concurrency group, including manual tests. A running sender is never cancelled by a newer trigger.
- GitHub schedules can run late. Keep the external scheduler configured for checks within the window; this workflow cannot guarantee an exact execution minute.

## State and delivery guarantees

The state file records `last_automated_notification_date` only after Slack delivery succeeds. The legacy `last_automated_check_date` does not suppress delivery. Both numeric IDs and shortcodes preserve deduplication across source changes. A different candidate must also be newer than the saved timestamp; stale or ambiguous results fail without sending or changing state. Apify timestamps have second precision. Legacy day-precision state requires a candidate beyond that whole day to prove it is newer.

The workflow persists state to `main`, retrying a rejected push up to three times. It rebases only if remote history has moved forward without changing the state file; it refuses conflicting state rather than overwriting another writer.

This is not an exactly-once delivery guarantee. A crash, lost Slack response, or state-persistence failure after Slack accepts a message can leave delivery uncertain and allow a duplicate on a later run. Check Slack and the Actions logs before rerunning such failures. Workflow concurrency does not lock independent local processes or copies of this repository.

## First run behavior

- On the first run, the workflow saves the current latest Instagram post as the baseline
- The first run does not send a Slack message
- A later new post on the same day can still be sent; saving a baseline does not mark that day as notified.
- After that, the script only posts the latest update found during the day's 10:30-11:00 Asia/Seoul check
- A manual run with `dry_run` disabled and `force_notify` enabled sends a test notification even when nothing new was posted

## Optional local test

Python 3.12 or later and the locked dependencies are required. Supply `APIFY_TOKEN` securely in the environment; never commit it to a config or print it. No local browser installation is required for normal operation.

```sh
uv sync --locked
uv run python instagram_slack_notifier.py --config config.example.json --dry-run
```

On Windows without an IANA timezone database, add `--with tzdata` to `uv run`. Browser diagnosis additionally needs `uv run playwright install chromium`.

For a manual delivery, first copy `config.example.json` to `config.json` and set your real Slack webhook URL. A normal run observes the time window and deduplication rules:

```powershell
uv run python .\instagram_slack_notifier.py --config .\config.json
```

To send a local test Slack message with the latest post:

```powershell
uv run python .\instagram_slack_notifier.py --config .\config.json --force-notify
```

## Development checks

```sh
uv sync --locked
uv run pytest
uv run ruff check .
uv run basedpyright
```

Tests isolate Instagram and Slack, use temporary state files, and exercise the workflow's actual Bash against temporary local Git remotes. They require no secrets and send no real Slack messages. Runtime and development dependencies are locked in `uv.lock`.

