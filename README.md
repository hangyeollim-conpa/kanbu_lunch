# Instagram to Slack Notifier

This repository checks the public Instagram profile `@lunch11_14` and sends one Slack message during the 10:30-11:00 Asia/Seoul window if a newer post exists since the previous daily check.

## Files

- `instagram_slack_notifier.py`: main checker script
- `config.example.json`: optional local test config template
- `.github/workflows/instagram-slack-notifier.yml`: daily GitHub Actions workflow

## Trigger setup

1. Open the repository on GitHub
2. Go to `Settings` -> `Secrets and variables` -> `Actions`
3. Add a new repository secret named `SLACK_WEBHOOK_URL`
4. Paste your Slack Incoming Webhook URL
5. Create a GitHub fine-grained personal access token for this repository with `Contents: Write`
6. In `cron-job.org`, create a daily job that sends a `POST` request to:

```text
https://api.github.com/repos/hangyeollim-conpa/kanbu_lunch/dispatches
```

7. Use these headers in `cron-job.org`:

```text
Accept: application/vnd.github+json
Authorization: Bearer YOUR_GITHUB_TOKEN
Content-Type: application/json
X-GitHub-Api-Version: 2026-03-10
```

8. Use this JSON request body:

```json
{"event_type":"instagram-slack-notifier"}
```

## Schedule

- The workflow also has a GitHub Actions fallback schedule at `10:38`, `10:46`, and `10:54` KST
- `cron-job.org` can call the same workflow during the `10:30-11:00` window in `Asia/Seoul`
- A simple `cron-job.org` recommendation is `10:38` every day
- If you want extra redundancy, add additional `cron-job.org` jobs at `10:46` and `10:54`
- The script only allows automatic notifications during the `10:30-11:00` KST window and still sends at most once per day
- You can also run it manually from the `Actions` tab with `Run workflow`
- Manual runs send the latest post to Slack by default so you can confirm the bot is working
- If both GitHub schedule and `cron-job.org` trigger on the same day, the script still sends at most once

## First run behavior

- On the first run, the workflow saves the current latest Instagram post as the baseline
- The first run does not send a Slack message
- After that, the script only posts the latest update found during the day's 10:30-11:00 Asia/Seoul check
- A manual run with `force_notify` enabled sends a test notification even when nothing new was posted

## Optional local test

1. Copy `config.example.json` to `config.json`
2. Replace `slack_webhook_url` with your real Slack Incoming Webhook URL
3. Run:

```powershell
python .\instagram_slack_notifier.py --config .\config.json --dry-run
```

To send a local test Slack message with the latest post:

```powershell
python .\instagram_slack_notifier.py --config .\config.json --force-notify
```

## Notes

- This setup uses Instagram's public web profile data instead of the official Instagram Graph API
- The target profile is currently public, so the lightweight approach works well
- If Instagram changes the web response format later, the script may need a small update
