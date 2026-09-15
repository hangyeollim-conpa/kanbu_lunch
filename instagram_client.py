import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Literal

INSTAGRAM_APP_ID = "936619743392459"
INSTAGRAM_FEED_URL_TEMPLATES = (
    "https://i.instagram.com/api/v1/feed/user/{username}/username/?count=12",
    "https://www.instagram.com/api/v1/feed/user/{username}/username/?count=12",
)
INSTAGRAM_PROFILE_URL_TEMPLATES = (
    "https://i.instagram.com/api/v1/users/web_profile_info/?username={username}",
    "https://www.instagram.com/api/v1/users/web_profile_info/?username={username}",
)
INSTAGRAM_REQUEST_HEADERS = (
    {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
            "Mobile/15E148 Safari/604.1"
        ),
        "x-ig-app-id": INSTAGRAM_APP_ID,
        "x-asbd-id": "129477",
        "accept-language": "en-US,en;q=0.9",
        "accept": "*/*",
        "x-requested-with": "XMLHttpRequest",
    },
    {
        "User-Agent": "Mozilla/5.0",
        "x-ig-app-id": INSTAGRAM_APP_ID,
        "accept-language": "en-US,en;q=0.9",
        "accept": "*/*",
    },
)


@dataclass
class Post:
    post_id: str
    shortcode: str
    permalink: str
    timestamp: int
    caption: str
    display_url: str
    is_pinned: bool | None
    timestamp_precision: Literal["second", "day"] = "second"


class InstagramAccessError(RuntimeError):
    def __init__(self, status_code: int, retry_after: str | None = None) -> None:
        self.status_code = status_code
        self.retry_after = retry_after
        if status_code == 429:
            detail = "Instagram rate limit reached. Wait before the next scheduled attempt."
        else:
            detail = (
                "Instagram denied this unauthenticated API request."
            )
        if retry_after:
            detail += f" Retry-After: {retry_after}."
        super().__init__(f"HTTP {status_code}: {detail} No additional endpoints were tried.")


def fetch_instagram_profile(username: str) -> dict[str, Any]:
    last_error: Exception | None = None
    encoded_username = urllib.parse.quote(username)
    referer = f"https://www.instagram.com/{username}/"

    for url_templates, expected_payload in (
        (INSTAGRAM_FEED_URL_TEMPLATES, "feed"),
        (INSTAGRAM_PROFILE_URL_TEMPLATES, "profile"),
    ):
        for url_template in url_templates:
            url = url_template.format(username=encoded_username)

            for header_template in INSTAGRAM_REQUEST_HEADERS:
                headers = dict(header_template)
                headers["referer"] = referer
                request = urllib.request.Request(url, headers=headers)

                try:
                    with urllib.request.urlopen(request, timeout=30) as response:
                        body = response.read().decode("utf-8")
                except urllib.error.HTTPError as exc:
                    if exc.code in {401, 403, 429}:
                        raise InstagramAccessError(
                            exc.code, exc.headers.get("Retry-After")
                        ) from exc
                    last_error = exc
                    continue
                except urllib.error.URLError as exc:
                    last_error = exc
                    continue

                if not body.strip():
                    last_error = RuntimeError(f"Empty response body from {url}")
                    continue

                try:
                    payload = json.loads(body)
                except json.JSONDecodeError as exc:
                    last_error = exc
                    continue

                if payload.get("status") != "ok":
                    last_error = RuntimeError(f"Unexpected Instagram payload from {url}")
                    continue

                if expected_payload == "feed" and payload.get("items"):
                    print(f"Fetched Instagram feed from {url}")
                    return payload

                if expected_payload == "profile" and "data" in payload:
                    print(f"Fetched Instagram profile from {url}")
                    return payload

                if expected_payload == "feed":
                    last_error = RuntimeError(f"Instagram feed response contained no items: {url}")
                else:
                    last_error = RuntimeError(
                        f"Instagram profile response contained no data: {url}"
                    )

    if last_error is None:
        raise RuntimeError("Instagram profile request failed for an unknown reason.")

    raise RuntimeError(f"Instagram profile request failed after fallback attempts: {last_error}")


def extract_latest_post(profile_data: dict[str, Any]) -> Post:
    if profile_data.get("items"):
        return extract_latest_post_from_feed(profile_data)

    return extract_latest_post_from_profile(profile_data)


def extract_latest_post_from_feed(feed_data: dict[str, Any]) -> Post:
    items = feed_data["items"]

    if not items:
        raise RuntimeError("No posts were found in the Instagram feed response.")

    user_id = str(feed_data.get("user", {}).get("pk", ""))

    def to_post(item: dict[str, Any]) -> Post:
        caption_data = item.get("caption")
        caption = caption_data.get("text", "") if isinstance(caption_data, dict) else ""
        shortcode = item["code"]
        image_candidates = item.get("image_versions2", {}).get("candidates", [])
        display_url = (
            image_candidates[0]["url"] if image_candidates else item.get("display_uri", "")
        )
        pinned_user_ids = {str(value) for value in item.get("timeline_pinned_user_ids", [])}
        is_pinned = bool(user_id and user_id in pinned_user_ids)

        return Post(
            post_id=str(item.get("pk") or item["id"]),
            shortcode=shortcode,
            permalink=f"https://www.instagram.com/p/{shortcode}/",
            timestamp=int(item["taken_at"]),
            caption=caption.strip(),
            display_url=display_url,
            is_pinned=is_pinned,
        )

    posts = [to_post(item) for item in items]
    return max(posts, key=lambda post: post.timestamp)


def extract_latest_post_from_profile(profile_data: dict[str, Any]) -> Post:
    user = profile_data["data"]["user"]
    edges = user["edge_owner_to_timeline_media"]["edges"]

    if not edges:
        raise RuntimeError("No posts were found on the Instagram profile.")

    def to_post(edge: dict[str, Any]) -> Post:
        node = edge["node"]
        caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
        caption = caption_edges[0]["node"]["text"] if caption_edges else ""
        shortcode = node["shortcode"]
        return Post(
            post_id=node["id"],
            shortcode=shortcode,
            permalink=f"https://www.instagram.com/p/{shortcode}/",
            timestamp=int(node["taken_at_timestamp"]),
            caption=caption.strip(),
            display_url=node.get("display_url", ""),
            is_pinned=bool(node.get("pinned_for_users")),
        )

    posts = [to_post(edge) for edge in edges]
    return max(posts, key=lambda post: post.timestamp)
