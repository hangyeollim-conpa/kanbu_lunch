import json
import urllib.error
import urllib.request
from email.message import Message
from io import BytesIO
from typing import NoReturn

import pytest

import instagram_client as app


@pytest.mark.parametrize("status", [401, 403, 429])
def test_rejected_access_stops_additional_requests(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
) -> None:
    # Given an upstream rejection, including its backoff instruction.
    requests: list[str] = []
    headers = Message()
    headers["Retry-After"] = "900"

    def reject(request: urllib.request.Request, *, timeout: int) -> NoReturn:
        requests.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, status, "Rejected", headers, None)

    monkeypatch.setattr(urllib.request, "urlopen", reject)
    # When fetching a profile.
    with pytest.raises(RuntimeError, match=str(status)) as raised:
        app.fetch_instagram_profile("test_lunch")
    # Then authentication/rate-limit rejection is never retried across hosts or headers.
    assert len(requests) == 1
    if status == 429:
        assert "900" in str(raised.value)


def test_invalid_response_can_fall_back_to_valid_feed(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given one invalid response followed by a valid public feed.
    bodies = iter(
        [
            b"not json",
            json.dumps(
                {
                    "status": "ok",
                    "items": [{"pk": "1", "code": "post", "taken_at": 10}],
                }
            ).encode(),
        ]
    )

    def respond(request: urllib.request.Request, *, timeout: int) -> BytesIO:
        return BytesIO(next(bodies))

    monkeypatch.setattr(urllib.request, "urlopen", respond)
    # When the feed is retrieved and parsed.
    post = app.extract_latest_post(app.fetch_instagram_profile("test_lunch"))
    # Then format fallbacks still work independently of access rejection.
    assert post.post_id == "1"


def test_feed_selects_latest_timestamp_instead_of_pinned_order() -> None:
    # Given an old pinned post ordered ahead of the latest menu.
    payload = {
        "user": {"pk": "user"},
        "items": [
            {"pk": "old", "code": "old", "taken_at": 100, "timeline_pinned_user_ids": ["user"]},
            {"pk": "new", "code": "new", "taken_at": 200},
        ],
    }
    # When selecting the post.
    post = app.extract_latest_post(payload)
    # Then chronological ordering wins over timeline position.
    assert post.post_id == "new"


def test_profile_fallback_preserves_caption_and_image() -> None:
    # Given the alternate public profile response shape.
    payload = {
        "data": {
            "user": {
                "edge_owner_to_timeline_media": {
                    "edges": [
                        {
                            "node": {
                                "id": "1",
                                "shortcode": "post",
                                "taken_at_timestamp": 100,
                                "display_url": "https://example.com/menu.jpg",
                                "edge_media_to_caption": {"edges": [{"node": {"text": " Menu "}}]},
                            }
                        }
                    ]
                }
            }
        }
    }
    # When parsing its post.
    post = app.extract_latest_post(payload)
    # Then the media and caption remain available to the notifier.
    assert (post.caption, post.display_url) == ("Menu", "https://example.com/menu.jpg")
