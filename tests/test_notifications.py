import json
import urllib.error
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

import instagram_slack_notifier as app


def test_later_post_is_sent_after_first_check_finds_nothing(
    config_path: Path,
    provide_post: Callable[[str, int], None],
    deliveries: list[str],
) -> None:
    # Given yesterday's post was sent, and today's first check has no update.
    state_path = config_path.parent / "state.json"
    state_path.write_text(json.dumps({"last_notified_post_id": "old"}), encoding="utf-8")
    provide_post("old", 100)
    assert app.main() == 0
    provide_post("new", 200)
    # When a new post arrives before the next scheduled check.
    result = app.main()
    # Then it is delivered and the successful-send date is recorded.
    assert result == 0
    assert len(deliveries) == 1
    assert "/new/" in deliveries[0]
    assert json.loads(state_path.read_text())["last_automated_notification_date"] == "2026-09-11"


@pytest.mark.parametrize("hour,minute", [(10, 29), (11, 1), (15, 27)])
def test_outside_window_skips_fetch(
    config_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    hour: int,
    minute: int,
) -> None:
    # Given an ineligible run and an external API that must not be contacted.
    monkeypatch.setattr(app, "now_kst", lambda: datetime(2026, 9, 11, hour, minute, tzinfo=app.KST))
    # When the automatic CLI executes.
    result = app.main()
    # Then it skips successfully without fetching or changing state.
    assert result == 0
    assert not (config_path.parent / "state.json").exists()


def test_already_sent_today_skips_fetch(config_path: Path) -> None:
    # Given a successful delivery already recorded for today.
    state_path = config_path.parent / "state.json"
    saved = json.dumps({"last_automated_notification_date": "2026-09-11"})
    state_path.write_text(saved, encoding="utf-8")
    # When a duplicate trigger runs.
    result = app.main()
    # Then it does not contact Instagram or modify state.
    assert result == 0
    assert state_path.read_text(encoding="utf-8") == saved


def test_legacy_check_marker_does_not_block_new_post(
    config_path: Path,
    provide_post: Callable[[str, int], None],
    deliveries: list[str],
) -> None:
    # Given old state which cannot distinguish a check from a delivery.
    state_path = config_path.parent / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "last_notified_post_id": "old",
                "last_automated_check_date": "2026-09-11",
            }
        ),
        encoding="utf-8",
    )
    provide_post("new", 200)
    # When a different post is checked.
    result = app.main()
    # Then ID deduplication still allows this update.
    assert result == 0
    assert len(deliveries) == 1


def test_baseline_does_not_prevent_later_update(
    config_path: Path,
    provide_post: Callable[[str, int], None],
    deliveries: list[str],
) -> None:
    # Given a first run with no state, which should only establish a baseline.
    provide_post("old", 100)
    assert app.main() == 0
    assert deliveries == []
    provide_post("new", 200)
    # When a new post arrives later in the window.
    result = app.main()
    # Then it can be sent that same day.
    assert result == 0
    assert len(deliveries) == 1


def test_failed_slack_delivery_preserves_retryability(
    config_path: Path,
    provide_post: Callable[[str, int], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given an existing baseline and an unavailable Slack webhook.
    state_path = config_path.parent / "state.json"
    saved = json.dumps({"last_notified_post_id": "old"})
    state_path.write_text(saved, encoding="utf-8")
    provide_post("new", 200)

    def fail_delivery(webhook_url: str, payload: dict[str, str]) -> None:
        raise urllib.error.URLError("simulated unavailable webhook")

    monkeypatch.setattr(app, "post_to_slack", fail_delivery)
    # When delivery fails.
    result = app.main()
    # Then it reports failure without marking the post or day sent.
    assert result == 1
    assert state_path.read_text(encoding="utf-8") == saved


@pytest.mark.parametrize("option", ["--dry-run", "--force-notify"])
def test_manual_modes_preserve_state(
    config_path: Path,
    provide_post: Callable[[str, int], None],
    deliveries: list[str],
    monkeypatch: pytest.MonkeyPatch,
    option: str,
) -> None:
    # Given a manual run outside the automatic window, with a completed day.
    state_path = config_path.parent / "state.json"
    saved = json.dumps({"last_automated_notification_date": "2026-09-11"})
    state_path.write_text(saved, encoding="utf-8")
    provide_post("new", 200)
    monkeypatch.setattr(app, "now_kst", lambda: datetime(2026, 9, 11, 15, 0, tzinfo=app.KST))
    monkeypatch.setattr("sys.argv", ["notifier", "--config", str(config_path), option])
    # When manually inspecting or requesting a test notification.
    result = app.main()
    # Then automatic state is unchanged and only force mode sends.
    assert result == 0
    assert state_path.read_text(encoding="utf-8") == saved
    assert len(deliveries) == (1 if option == "--force-notify" else 0)
