import json
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from typing import Final

import pytest

import instagram_slack_notifier as app

REAL_SLACK_DELIVERY: Final = app.post_to_slack


@pytest.mark.parametrize("accepted", [True, False], ids=["ok", "unexpected-response"])
def test_delivery_persists_state_only_after_webhook_accepts(
    config_path: Path,
    provide_post: Callable[[str, int], None],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    accepted: bool,
) -> None:
    # Given a new post and a loopback webhook with the real HTTP delivery adapter.
    state_path = config_path.parent / "state.json"
    prior_state = json.dumps({"last_notified_post_id": "old"})
    state_path.write_text(prior_state, encoding="utf-8")
    provide_post("new", 200)
    monkeypatch.setattr(app, "post_to_slack", REAL_SLACK_DELIVERY)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    requests: list[tuple[str, str, bytes, str]] = []

    class WebhookHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            requests.append(
                (
                    self.path,
                    self.headers.get("Content-Type", ""),
                    body,
                    state_path.read_text(encoding="utf-8"),
                )
            )
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok" if accepted else b"invalid_payload")

    with HTTPServer(("127.0.0.1", 0), WebhookHandler) as server:
        config_path.write_text(
            json.dumps(
                {
                    "instagram_username": "test_lunch",
                    "instagram_profile_url": "https://www.instagram.com/test_lunch/",
                    "slack_webhook_url": f"http://127.0.0.1:{server.server_port}/webhook",
                    "state_file": "state.json",
                }
            ),
            encoding="utf-8",
        )
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        try:
            # When the automatic notifier posts through an actual HTTP connection.
            result = app.main()
        finally:
            server.shutdown()
            thread.join(timeout=2)

    # Then its JSON is delivered once, with state unchanged until acceptance.
    assert not thread.is_alive()
    assert len(requests) == 1
    path, content_type, body, state_during_request = requests[0]
    assert path == "/webhook"
    assert content_type == "application/json"
    assert json.loads(body) == {
        "text": "Instagram update detected: @test_lunch https://www.instagram.com/p/new/",
        "blocks": [
            {
                "type": "image",
                "image_url": "https://example.com/menu.jpg",
                "alt_text": "test_lunch Instagram post",
            }
        ],
    }
    assert state_during_request == prior_state
    assert result == (0 if accepted else 1)
    if accepted:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert state["last_notified_post_id"] == "new"
        assert state["last_automated_notification_date"] == "2026-09-11"
    else:
        assert state_path.read_text(encoding="utf-8") == prior_state
        assert "Failed to post to Slack" in capsys.readouterr().err
