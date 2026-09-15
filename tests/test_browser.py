import json
from unittest.mock import MagicMock, patch

import pytest
from playwright.sync_api import Page

from instagram_browser import read_public_post_time, read_public_profile
from instagram_client import Post
from instagram_public import PublicProfileError


def test_public_browser_reads_tiles_without_opening_post_details() -> None:
    page = MagicMock(spec=Page)
    page.goto.return_value.status = 200
    page.url = "https://www.instagram.com/test_lunch/"
    page.get_by_role.return_value.count.return_value = 0
    page.locator.return_value.evaluate_all.return_value = json.dumps(
        [
            {
                "permalink": "https://www.instagram.com/test_lunch/p/menu/",
                "description": "Photo by @test_lunch on September 09, 2026.",
                "image_url": "https://scontent.cdninstagram.com/menu.jpg",
            }
        ]
    )
    post = read_public_profile(page, "test_lunch")
    assert post.shortcode == "menu"
    assert post.timestamp_precision == "day"
    page.goto.assert_called_once()
    page.get_by_role.return_value.click.assert_not_called()


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_public_browser_stops_on_http_denial(status: int) -> None:
    page = MagicMock(spec=Page)
    page.goto.return_value.status = status
    page.goto.return_value.all_headers.return_value = {}
    page.goto.return_value.body.return_value = b""
    with pytest.raises(PublicProfileError, match=f"HTTP {status}"):
        read_public_profile(page, "test_lunch")
    page.goto.assert_called_once()
    page.locator.assert_not_called()


def test_http_diagnostics_keep_evidence_without_session_secrets(capsys) -> None:
    page = MagicMock(spec=Page)
    page.goto.return_value.status = 429
    page.goto.return_value.all_headers.return_value = {
        "retry-after": "600", "set-cookie": "secret-cookie",
    }
    page.goto.return_value.body.return_value = b"Too many requests. secret-token"
    with pytest.raises(PublicProfileError, match="HTTP 429"):
        read_public_profile(page, "test_lunch")
    output = capsys.readouterr().err
    assert '"retry-after": "600"' in output
    assert '"too many requests"' in output
    assert '"body_sha256"' in output
    assert "secret" not in output
    page.goto.assert_called_once()


def test_public_browser_refuses_login_redirect() -> None:
    page = MagicMock(spec=Page)
    page.goto.return_value.status = 200
    page.url = "https://www.instagram.com/accounts/login/"
    with pytest.raises(PublicProfileError, match="requires login"):
        read_public_profile(page, "test_lunch")
    page.locator.assert_not_called()


def test_same_day_candidates_use_detail_times_instead_of_tile_order() -> None:
    page = MagicMock(spec=Page)
    page.goto.return_value.status = 200
    page.url = "https://www.instagram.com/test_lunch/"
    page.get_by_role.return_value.count.return_value = 0
    page.locator.return_value.evaluate_all.return_value = json.dumps([
        {"permalink": f"https://www.instagram.com/p/{code}/",
         "description": "Photo by @test_lunch on September 13, 2026.",
         "image_url": "https://scontent.cdninstagram.com/menu.jpg"}
        for code in ("Older", "Latest")
    ])
    older = Post("Older", "Older", "", 100, "", "", None)
    latest = Post("Latest", "Latest", "", 200, "", "", None)
    with patch("instagram_browser.read_public_post_time", side_effect=[older, latest]) as read:
        assert read_public_profile(page, "test_lunch").shortcode == "Latest"
        assert read.call_count == 2


@pytest.mark.parametrize("values", [[], ["bad"], ["2026-09-14"],
                                   ["2026-09-14T06:43:24Z", "2026-09-14T06:43:25Z"]])
def test_detail_time_rejects_missing_invalid_or_conflicting_values(values) -> None:
    page = MagicMock(spec=Page)
    page.goto.return_value.status = 200
    page.url = "https://www.instagram.com/p/Latest/"
    page.locator.return_value.evaluate_all.return_value = values
    post = Post("Latest", "Latest", page.url, 0, "", "", None)
    with pytest.raises(PublicProfileError, match="publication time"):
        read_public_post_time(page, post)


def test_detail_time_uses_permalink_timestamp_and_preserves_image() -> None:
    page = MagicMock(spec=Page)
    page.goto.return_value.status = 200
    page.url = "https://www.instagram.com/p/Latest/"
    page.locator.return_value.evaluate_all.return_value = ["2026-09-14T06:43:24.000Z"]
    post = Post("Latest", "Latest", page.url, 0, "", "https://cdninstagram.com/a.jpg", None)
    result = read_public_post_time(page, post)
    assert result.timestamp == 1789368204
    assert result.timestamp_precision == "second"
    assert result.display_url == post.display_url
    page.locator.assert_called_once_with('a[href$="/p/Latest/"] time[datetime]')
