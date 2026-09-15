import json
from datetime import UTC, datetime
from typing import TypedDict

import pytest

from instagram_public import PublicProfileError, select_latest_public_post


class Tile(TypedDict):
    permalink: str
    description: str
    image_url: str


def tile(code: str = "Latest", date: str = "September 09, 2026") -> Tile:
    return {
        "permalink": f"https://www.instagram.com/lunch11_14/p/{code}/",
        "description": f"Photo by @lunch11_14 on {date}. 2026.09.11 menu",
        "image_url": "https://scontent-ssn1-1.cdninstagram.com/menu.jpg?token=public",
    }


def test_latest_when_pinned_notice_is_first() -> None:
    # Given
    tiles = [tile("Pinned", "July 14, 2025"), tile(), tile("Old", "September 08, 2026")]
    # When
    post = select_latest_public_post("lunch11_14", json.dumps(tiles))
    # Then
    assert post.shortcode == "Latest"
    assert post.post_id == "Latest"
    assert post.is_pinned is None


def test_publication_date_when_menu_has_a_later_date() -> None:
    # Given
    serialized = json.dumps([tile()])
    # When
    post = select_latest_public_post("lunch11_14", serialized)
    # Then
    assert datetime.fromtimestamp(post.timestamp, UTC).date().isoformat() == "2026-09-09"
    assert post.timestamp_precision == "day"


def test_deduplicates_when_same_shortcode_is_repeated() -> None:
    # Given
    first = tile()
    duplicate = tile()
    duplicate["permalink"] = "https://www.instagram.com/p/Latest/"
    # When
    post = select_latest_public_post("lunch11_14", json.dumps([first, duplicate]))
    # Then
    assert post.permalink == "https://www.instagram.com/p/Latest/"


def test_rejects_when_latest_date_is_ambiguous() -> None:
    # Given
    serialized = json.dumps([tile("One"), tile("Two")])
    # When / Then
    with pytest.raises(PublicProfileError, match="same publication day"):
        select_latest_public_post("lunch11_14", serialized)


@pytest.mark.parametrize("date", ["", "February 30, 2026", "Sept 09, 2026"])
def test_rejects_when_any_tile_has_unknown_publication_date(date: str) -> None:
    # Given
    serialized = json.dumps([tile("Unknown", date), tile("Older", "July 14, 2025")])
    # When / Then
    with pytest.raises(PublicProfileError, match="publication date"):
        select_latest_public_post("lunch11_14", serialized)


@pytest.mark.parametrize(
    "permalink",
    [
        "https://www.instagram.com.evil.test/p/Latest/",
        "https://evil.test/p/Latest/",
        "http://www.instagram.com/p/Latest/",
        "https://user@www.instagram.com/p/Latest/",
        "https://www.instagram.com/other/p/Latest/",
        "https://www.instagram.com/accounts/login/",
        "https://www.instagram.com/p/Latest/?redirect=evil",
    ],
)
def test_rejects_when_permalink_is_untrusted(permalink: str) -> None:
    # Given
    record = tile()
    record["permalink"] = permalink
    # When / Then
    with pytest.raises(PublicProfileError, match="permalink"):
        select_latest_public_post("lunch11_14", json.dumps([record]))


@pytest.mark.parametrize(
    "image_url",
    [
        "https://cdninstagram.com.evil.test/menu.jpg",
        "https://evilcdninstagram.com/menu.jpg",
        "http://scontent.cdninstagram.com/menu.jpg",
        "https://user@scontent.cdninstagram.com/menu.jpg",
        "https://scontent.cdninstagram.com:123/menu.jpg",
        "https://127.0.0.1/menu.jpg",
        "data:image/png;base64,abc",
        "https://[invalid/menu.jpg",
    ],
)
def test_rejects_when_image_is_untrusted(image_url: str) -> None:
    # Given
    record = tile()
    record["image_url"] = image_url
    # When / Then
    with pytest.raises(PublicProfileError, match="image URL"):
        select_latest_public_post("lunch11_14", json.dumps([record]))


@pytest.mark.parametrize("owner", ["another_account", "lunch11_14.evil", "lunch11_140"])
def test_rejects_when_description_names_another_owner(owner: str) -> None:
    # Given
    record = tile()
    record["description"] = f"Photo by @{owner} on September 09, 2026. menu"
    # When / Then
    with pytest.raises(PublicProfileError, match="owner"):
        select_latest_public_post("lunch11_14", json.dumps([record]))


@pytest.mark.parametrize("serialized", ["not JSON", "{}", "null", '[{"permalink": 3}]'])
def test_rejects_when_browser_json_is_malformed(serialized: str) -> None:
    # Given / When / Then
    with pytest.raises(PublicProfileError, match="tile data"):
        select_latest_public_post("lunch11_14", serialized)


def test_rejects_when_login_screen_has_no_tiles() -> None:
    # Given / When / Then
    with pytest.raises(PublicProfileError, match="No public posts"):
        select_latest_public_post("lunch11_14", "[]")


def test_rejects_when_duplicate_shortcode_has_conflicting_dates() -> None:
    # Given
    serialized = json.dumps([tile(), tile(date="September 08, 2026")])
    # When / Then
    with pytest.raises(PublicProfileError, match="conflicting publication dates"):
        select_latest_public_post("lunch11_14", serialized)


def test_accepts_when_owner_has_no_at_and_image_uses_fbcdn() -> None:
    # Given
    record = tile()
    record["description"] = record["description"].replace("@lunch11_14", "lunch11_14")
    record["image_url"] = "https://scontent.fbcdn.net/menu.jpg"
    # When
    post = select_latest_public_post("lunch11_14", json.dumps([record]))
    # Then
    assert post.display_url == record["image_url"]
