import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_CONFIG_NAME = "config.json"
DEFAULT_STATE_NAME = ".instagram_state.json"
INSTAGRAM_APP_ID = "936619743392459"
KST = ZoneInfo("Asia/Seoul")
NOTIFICATION_START_HOUR_KST = 10
NOTIFICATION_START_MINUTE_KST = 30
NOTIFICATION_END_HOUR_KST = 11
NOTIFICATION_END_MINUTE_KST = 0
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
    is_pinned: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check a public Instagram profile and post new updates to Slack."
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_NAME,
        help=f"Path to config JSON. Defaults to {DEFAULT_CONFIG_NAME}.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and print the latest detected post without sending to Slack.",
    )
    parser.add_argument(
        "--force-notify",
        action="store_true",
        help="Send the latest post to Slack even if it is not new.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def print_json(payload: dict[str, Any]) -> None:
    try:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def now_kst() -> datetime:
    return datetime.now(KST)


def is_automatic_notification_window(current_kst: datetime) -> bool:
    current_time = (current_kst.hour, current_kst.minute)
    start_time = (NOTIFICATION_START_HOUR_KST, NOTIFICATION_START_MINUTE_KST)
    end_time = (NOTIFICATION_END_HOUR_KST, NOTIFICATION_END_MINUTE_KST)
    return start_time <= current_time <= end_time


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
                except (urllib.error.HTTPError, urllib.error.URLError) as exc:
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
                    last_error = RuntimeError(f"Instagram profile response contained no data: {url}")

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
        display_url = image_candidates[0]["url"] if image_candidates else item.get("display_uri", "")
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


def format_timestamp(timestamp: int) -> str:
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone(KST)
    return dt.strftime("%Y-%m-%d %H:%M:%S KST")


def build_slack_payload(
    profile_url: str,
    username: str,
    post: Post,
    force_notify: bool = False,
) -> dict[str, Any]:
    summary = "Instagram notifier test" if force_notify else "Instagram update detected"
    text = f"{summary}: @{username} {post.permalink}"

    return {
        "text": text,
        "blocks": [
            {
                "type": "image",
                "image_url": post.display_url,
                "alt_text": f"{username} Instagram post",
            },
        ],
    }


def post_to_slack(webhook_url: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = response.read().decode("utf-8").strip()
        if result != "ok":
            raise RuntimeError(f"Slack webhook returned unexpected response: {result}")


def resolve_path(base_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base_dir / path


def load_state(state_path: Path) -> dict[str, Any]:
    if state_path.exists():
        return load_json(state_path)
    return {}


def load_previous_post_id(state: dict[str, Any]) -> str | None:
    previous_post_id = state.get("last_notified_post_id")
    if previous_post_id is None:
        previous_post_id = state.get("last_seen_post_id")
    return str(previous_post_id) if previous_post_id is not None else None


def load_last_automated_check_date(state: dict[str, Any]) -> str | None:
    value = state.get("last_automated_check_date")
    return str(value) if value else None


def save_state(
    state_path: Path,
    state: dict[str, Any],
    *,
    post: Post | None = None,
    automated_check_date: str | None = None,
) -> None:
    next_state = dict(state)

    if post is not None:
        next_state["last_notified_post_id"] = post.post_id
        next_state["last_notified_shortcode"] = post.shortcode
        next_state["last_notified_timestamp"] = post.timestamp
        next_state["last_seen_post_id"] = post.post_id
        next_state["last_seen_shortcode"] = post.shortcode
        next_state["last_seen_timestamp"] = post.timestamp

    if automated_check_date is not None:
        next_state["last_automated_check_date"] = automated_check_date

    save_json(
        state_path,
        next_state,
    )


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).resolve()

    if not config_path.exists():
        print(
            f"Config file not found: {config_path}\n"
            f"Copy config.example.json to {config_path.name} and fill it in first.",
            file=sys.stderr,
        )
        return 1

    config = load_json(config_path)
    base_dir = config_path.parent
    state_path = resolve_path(base_dir, config.get("state_file", DEFAULT_STATE_NAME))
    notify_on_first_run = bool(config.get("notify_on_first_run", False))
    username = config["instagram_username"]
    profile_url = config["instagram_profile_url"]
    webhook_url = config.get("slack_webhook_url", "")

    try:
        profile_data = fetch_instagram_profile(username)
        post = extract_latest_post(profile_data)
    except (KeyError, urllib.error.URLError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"Failed to fetch Instagram profile: {exc}", file=sys.stderr)
        return 1

    print_json(
        {
            "latest_post_id": post.post_id,
            "shortcode": post.shortcode,
            "permalink": post.permalink,
            "timestamp": post.timestamp,
            "formatted_time": format_timestamp(post.timestamp),
            "is_pinned": post.is_pinned,
            "caption": post.caption,
        }
    )

    if args.dry_run:
        return 0

    state = load_state(state_path)
    previous_post_id = load_previous_post_id(state)
    last_automated_check_date = load_last_automated_check_date(state)
    current_kst = now_kst()
    current_kst_date = current_kst.date().isoformat()
    if args.force_notify:
        if not webhook_url:
            print("Missing slack_webhook_url in config.json.", file=sys.stderr)
            return 1

        try:
            payload = build_slack_payload(
                profile_url=profile_url,
                username=username,
                post=post,
                force_notify=True,
            )
            post_to_slack(webhook_url, payload)
        except (urllib.error.URLError, RuntimeError) as exc:
            print(f"Failed to post to Slack: {exc}", file=sys.stderr)
            return 1

        print("Manual test notification sent to Slack. Automated state was not changed.")
        return 0

    if not is_automatic_notification_window(current_kst):
        print(
            "Outside the 10:30-11:00 KST notification window. "
            f"Current Asia/Seoul time: {current_kst.strftime('%Y-%m-%d %H:%M:%S KST')}"
        )
        return 0

    if last_automated_check_date == current_kst_date:
        print(
            "Today's automatic 10:30-11:00 KST check has already been completed. "
            "Slack message was not sent."
        )
        return 0

    if previous_post_id == post.post_id:
        save_state(
            state_path,
            state,
            automated_check_date=current_kst_date,
        )
        print("No new Instagram post found since the last 10:30-11:00 KST notification.")
        return 0

    if previous_post_id is None and not notify_on_first_run:
        save_state(
            state_path,
            state,
            post=post,
            automated_check_date=current_kst_date,
        )
        print("First scheduled 10:30-11:00 KST run detected. State saved without sending a Slack message.")
        return 0

    if not webhook_url:
        print("Missing slack_webhook_url in config.json.", file=sys.stderr)
        return 1

    try:
        payload = build_slack_payload(
            profile_url=profile_url,
            username=username,
            post=post,
        )
        post_to_slack(webhook_url, payload)
    except (urllib.error.URLError, RuntimeError) as exc:
        print(f"Failed to post to Slack: {exc}", file=sys.stderr)
        return 1

    save_state(
        state_path,
        state,
        post=post,
        automated_check_date=current_kst_date,
    )
    print("Latest Instagram post was sent for today's 10:30-11:00 KST check.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
