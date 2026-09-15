import json
from unittest.mock import MagicMock

import pytest
from playwright.sync_api import Page

from instagram_browser import read_public_profile
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
    with pytest.raises(PublicProfileError, match=f"HTTP {status}"):
        read_public_profile(page, "test_lunch")
    page.goto.assert_called_once()
    page.locator.assert_not_called()


def test_public_browser_refuses_login_redirect() -> None:
    page = MagicMock(spec=Page)
    page.goto.return_value.status = 200
    page.url = "https://www.instagram.com/accounts/login/"
    with pytest.raises(PublicProfileError, match="requires login"):
        read_public_profile(page, "test_lunch")
    page.locator.assert_not_called()
