import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

import instagram_slack_notifier as app


@pytest.fixture
def config_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "instagram_username": "test_lunch",
                "instagram_profile_url": "https://www.instagram.com/test_lunch/",
                "slack_webhook_url": "https://hooks.slack.com/services/TEST/ONLY/FAKE",
                "state_file": "state.json",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("sys.argv", ["instagram_slack_notifier.py", "--config", str(path)])
    monkeypatch.setattr(app, "now_kst", lambda: datetime(2026, 9, 11, 10, 38, tzinfo=app.KST))

    def no_network(username: str) -> None:
        pytest.fail(f"Unexpected external fetch for {username}")

    def no_slack(webhook_url: str, payload: dict[str, str]) -> None:
        pytest.fail("Unexpected Slack delivery")

    monkeypatch.setattr(app, "fetch_latest_public_post", no_network)
    monkeypatch.setattr(app, "post_to_slack", no_slack)
    return path


@pytest.fixture
def provide_post(monkeypatch: pytest.MonkeyPatch) -> Callable[[str, int], None]:
    def provide(post_id: str, timestamp: int) -> None:
        post = app.Post(
            post_id,
            post_id,
            f"https://www.instagram.com/p/{post_id}/",
            timestamp,
            "Lunch",
            "https://example.com/menu.jpg",
            False,
        )
        monkeypatch.setattr(app, "fetch_latest_public_post", lambda username: post)

    return provide


@pytest.fixture
def deliveries(monkeypatch: pytest.MonkeyPatch, config_path: Path) -> list[str]:
    sent: list[str] = []

    def record(webhook_url: str, payload: dict[str, str]) -> None:
        sent.append(payload["text"])

    monkeypatch.setattr(app, "post_to_slack", record)
    return sent
