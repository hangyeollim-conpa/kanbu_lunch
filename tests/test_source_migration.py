import json
from collections.abc import Callable
from pathlib import Path

import instagram_slack_notifier as app


def test_browser_shortcode_keeps_legacy_numeric_id_deduplication(
    config_path: Path,
    provide_post: Callable[[str, int], None],
    deliveries: list[str],
) -> None:
    state_path = config_path.parent / "state.json"
    original = json.dumps({"last_notified_post_id": "123456", "last_notified_shortcode": "same"})
    state_path.write_text(original, encoding="utf-8")
    provide_post("same", 200)
    assert app.main() == 0
    assert deliveries == []
    assert state_path.read_text(encoding="utf-8") == original
