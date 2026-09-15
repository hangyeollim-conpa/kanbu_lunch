import hashlib
import json
import re
import sys

from playwright.sync_api import Error as BrowserError
from playwright.sync_api import Page, Response, sync_playwright

from instagram_client import Post
from instagram_public import PublicProfileError, select_latest_public_post

TILE_SELECTOR = "main a[href*='/p/']"
TILE_SCRIPT = """links => JSON.stringify(links.flatMap(link => {
    const img = link.querySelector('img');
    if (!img) return [];
    return [{permalink: link.href, description: img.alt,
             image_url: img.currentSrc || img.src}];
}))"""


def log_http_diagnostics(response: Response) -> None:
    headers = response.all_headers()
    details: dict[str, object] = {
        "status": response.status,
        "headers": {
            key: headers[key]
            for key in (
                "date", "retry-after", "content-type", "server",
                "x-ig-error-code", "x-fb-error-code", "ratelimit-limit",
                "ratelimit-remaining", "ratelimit-reset",
            )
            if key in headers
        },
    }
    try:
        body = response.body()
        text = body.decode("utf-8", errors="replace").lower()
        # Only known messages are logged: raw HTML can contain session tokens.
        details.update({
            "body_bytes": len(body),
            "body_sha256": hashlib.sha256(body).hexdigest(),
            "body_markers": [
                marker for marker in (
                    "too many requests", "please wait a few minutes",
                    "try again later", "rate limit", "feedback_required",
                    "login_required", "challenge_required", "sentry_block",
                    "ip address", "automated behavior", "temporarily blocked",
                ) if marker in text
            ],
        })
    except BrowserError:
        details["body_unavailable"] = True
    print("Instagram HTTP diagnostics: " + json.dumps(details), file=sys.stderr)


def read_public_profile(page: Page, username: str) -> Post:
    if re.fullmatch(r"[A-Za-z0-9_.]{1,30}", username) is None:
        raise PublicProfileError("Invalid Instagram username.")
    response = page.goto(
        f"https://www.instagram.com/{username}/",
        wait_until="domcontentloaded",
        timeout=45_000,
    )
    if response is None or response.status >= 400:
        status = response.status if response is not None else "unavailable"
        if response is not None:
            log_http_diagnostics(response)
        raise PublicProfileError(f"Public profile returned HTTP {status}; no retries attempted.")
    if "/accounts/login" in page.url or "/challenge" in page.url:
        raise PublicProfileError("Public profile requires login or verification.")
    close_button = page.get_by_role("button", name=re.compile(r"^(Close|닫기)$"))
    if close_button.count() == 1 and close_button.is_visible():
        close_button.click(timeout=5_000)
    page.locator(f"{TILE_SELECTOR} img").first.wait_for(state="visible", timeout=30_000)
    serialized: object = page.locator(TILE_SELECTOR).evaluate_all(TILE_SCRIPT)
    if not isinstance(serialized, str):
        raise PublicProfileError("Public profile returned invalid tile data.")
    return select_latest_public_post(username, serialized)


def fetch_latest_public_post(username: str) -> Post:
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch()
            try:
                context = browser.new_context(locale="en-US", timezone_id="UTC")
                try:
                    return read_public_profile(context.new_page(), username)
                finally:
                    context.close()
            finally:
                browser.close()
    except BrowserError as exc:
        raise PublicProfileError(
            "Browser could not read public posts. Check Chromium installation and public "
            "page availability; login-only pages are not supported. No retries attempted."
        ) from exc
