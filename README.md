# Instagram to Slack Notifier

This repository checks the public Instagram profile `@lunch11_14` and sends a Slack message only when a newer post appears.

## Files

- `instagram_slack_notifier.py`: main checker script
- `config.example.json`: optional local test config template
- `.github/workflows/instagram-slack-notifier.yml`: daily GitHub Actions workflow

## GitHub Actions setup

1. Open the repository on GitHub
2. Go to `Settings` -> `Secrets and variables` -> `Actions`
3. Add a new repository secret named `SLACK_WEBHOOK_URL`
4. Paste your Slack Incoming Webhook URL

## Schedule

- The workflow runs every day at `02:00 UTC`
- That equals `11:00 Asia/Seoul`
- You can also run it manually from the `Actions` tab with `Run workflow`
- GitHub scheduled workflows can start a few minutes late, so treat `11:00` as approximate

## First run behavior

- On the first run, the workflow saves the current latest Instagram post as the baseline
- The first run does not send a Slack message
- After that, only newer posts trigger Slack alerts

## Optional local test

1. Copy `config.example.json` to `config.json`
2. Replace `slack_webhook_url` with your real Slack Incoming Webhook URL
3. Run:

```powershell
python .\instagram_slack_notifier.py --config .\config.json --dry-run
```

## Notes

- This setup uses Instagram's public web profile data instead of the official Instagram Graph API
- The target profile is currently public, so the lightweight approach works well
- If Instagram changes the web response format later, the script may need a small update
