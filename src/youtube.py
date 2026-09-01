from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

import pandas as pd


VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
API_ROOT = "https://www.googleapis.com/youtube/v3"


class YouTubeAPIError(RuntimeError):
    def __init__(self, message: str, *, reason: str = "unknown", status: int | None = None):
        super().__init__(message)
        self.reason = reason
        self.status = status


@dataclass(frozen=True)
class VideoMetadata:
    video_id: str
    title: str
    channel_title: str
    published_at: str
    public_comment_count: int | None


def extract_video_id(value: str) -> str:
    """
    Accepts a raw 11-char video ID or common YouTube URL shapes:
    watch, youtu.be, shorts, embed and live.
    """
    value = (value or "").strip()

    if VIDEO_ID_RE.fullmatch(value):
        return value

    if "://" not in value:
        value = "https://" + value

    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("m."):
        host = host[2:]

    candidate: str | None = None

    if host == "youtu.be":
        candidate = parsed.path.strip("/").split("/")[0]

    elif host in {"youtube.com", "music.youtube.com"}:
        path_parts = [p for p in parsed.path.split("/") if p]

        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [None])[0]
        elif len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed", "live"}:
            candidate = path_parts[1]

    if candidate and VIDEO_ID_RE.fullmatch(candidate):
        return candidate

    raise ValueError("Enter a valid YouTube video URL or 11-character video ID.")


def _error_from_http(exc: HTTPError) -> YouTubeAPIError:
    reason = "http_error"
    message = f"YouTube API returned HTTP {exc.code}."

    try:
        payload = json.loads(exc.read().decode("utf-8"))
        error = payload.get("error", {})
        errors = error.get("errors", [])
        reason = errors[0].get("reason", reason) if errors else reason
        api_message = error.get("message")
        if api_message:
            message = api_message
    except Exception:
        pass

    friendly = {
        "commentsDisabled": "Comments are disabled for this video.",
        "quotaExceeded": "The YouTube API daily quota has been reached. Try again later.",
        "dailyLimitExceeded": "The YouTube API daily quota has been reached. Try again later.",
        "keyInvalid": "The YouTube API key is invalid.",
        "ipRefererBlocked": "The YouTube API key restriction rejected this request.",
        "forbidden": "YouTube rejected access to the comments for this video.",
    }

    return YouTubeAPIError(
        friendly.get(reason, message),
        reason=reason,
        status=exc.code,
    )


def _request_json(
    resource: str,
    params: dict,
    api_key: str,
    *,
    timeout: int = 15,
) -> dict:
    query = dict(params)
    query["key"] = api_key

    url = f"{API_ROOT}/{resource}?{urlencode(query)}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "CommentOps/1.0",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise _error_from_http(exc) from exc
    except URLError as exc:
        raise YouTubeAPIError(
            "Could not reach the YouTube API. Check the network connection.",
            reason="network_error",
        ) from exc


def _fetch_metadata(
    video_id: str,
    api_key: str,
    request_json: Callable[[str, dict, str], dict],
) -> VideoMetadata:
    payload = request_json(
        "videos",
        {
            "part": "snippet,statistics",
            "id": video_id,
            "fields": (
                "items(id,snippet(title,channelTitle,publishedAt),"
                "statistics(commentCount))"
            ),
        },
        api_key,
    )

    items = payload.get("items", [])
    if not items:
        raise YouTubeAPIError(
            "Video not found, private, or unavailable.",
            reason="videoNotFound",
            status=404,
        )

    item = items[0]
    snippet = item.get("snippet", {})
    statistics = item.get("statistics", {})

    raw_count = statistics.get("commentCount")
    try:
        comment_count = int(raw_count) if raw_count is not None else None
    except (TypeError, ValueError):
        comment_count = None

    return VideoMetadata(
        video_id=video_id,
        title=snippet.get("title", "Untitled video"),
        channel_title=snippet.get("channelTitle", "Unknown channel"),
        published_at=snippet.get("publishedAt", ""),
        public_comment_count=comment_count,
    )


def _fetch_comment_order(
    video_id: str,
    api_key: str,
    *,
    order: str,
    limit: int,
    request_json: Callable[[str, dict, str], dict],
) -> list[dict]:
    comments: list[dict] = []
    page_token: str | None = None

    while len(comments) < limit:
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": min(100, limit - len(comments)),
            "order": order,
            "textFormat": "plainText",
            "fields": (
                "nextPageToken,"
                "items(snippet(totalReplyCount,"
                "topLevelComment(id,snippet(textOriginal,likeCount,publishedAt,updatedAt))))"
            ),
        }

        if page_token:
            params["pageToken"] = page_token

        payload = request_json("commentThreads", params, api_key)

        for item in payload.get("items", []):
            thread_snippet = item.get("snippet", {})
            top = thread_snippet.get("topLevelComment", {})
            snippet = top.get("snippet", {})

            comment_id = top.get("id")
            text = (snippet.get("textOriginal") or "").strip()

            if not comment_id or not text:
                continue

            comments.append(
                {
                    "comment_id": comment_id,
                    "comment": text,
                    "likes": int(snippet.get("likeCount") or 0),
                    "published_at": snippet.get("publishedAt", ""),
                    "updated_at": snippet.get("updatedAt", ""),
                    "reply_count": int(thread_snippet.get("totalReplyCount") or 0),
                    "youtube_order": order,
                }
            )

            if len(comments) >= limit:
                break

        page_token = payload.get("nextPageToken")
        if not page_token:
            break

    return comments


def _dedupe_interleaved(left: Iterable[dict], right: Iterable[dict], limit: int) -> list[dict]:
    left = list(left)
    right = list(right)
    result: list[dict] = []
    seen: set[str] = set()

    max_len = max(len(left), len(right), 0)

    for index in range(max_len):
        for source in (left, right):
            if index >= len(source):
                continue

            item = source[index]
            key = item["comment_id"]

            if key in seen:
                continue

            seen.add(key)
            result.append(item)

            if len(result) >= limit:
                return result

    return result


def fetch_youtube_video(
    value: str,
    api_key: str,
    *,
    max_comments: int = 300,
    sampling: str = "balanced",
    request_json: Callable[[str, dict, str], dict] = _request_json,
) -> tuple[pd.DataFrame, VideoMetadata]:
    """
    Fetch public top-level comments for a YouTube video.

    sampling:
      - balanced: interleave relevance + recency and deduplicate
      - top: relevance order
      - latest: time order
    """
    if not api_key:
        raise ValueError("A YouTube API key is required.")

    if not 1 <= int(max_comments) <= 500:
        raise ValueError("max_comments must be between 1 and 500.")

    sampling = sampling.lower().strip()
    if sampling not in {"balanced", "top", "latest"}:
        raise ValueError("sampling must be balanced, top, or latest.")

    video_id = extract_video_id(value)
    metadata = _fetch_metadata(video_id, api_key, request_json)

    if sampling == "top":
        rows = _fetch_comment_order(
            video_id,
            api_key,
            order="relevance",
            limit=max_comments,
            request_json=request_json,
        )
    elif sampling == "latest":
        rows = _fetch_comment_order(
            video_id,
            api_key,
            order="time",
            limit=max_comments,
            request_json=request_json,
        )
    else:
        # Fetch both views. The extra quota is small (1 unit/page) and gives a
        # much better sample than using only "top" or only "latest".
        relevant = _fetch_comment_order(
            video_id,
            api_key,
            order="relevance",
            limit=max_comments,
            request_json=request_json,
        )
        recent = _fetch_comment_order(
            video_id,
            api_key,
            order="time",
            limit=max_comments,
            request_json=request_json,
        )
        rows = _dedupe_interleaved(relevant, recent, max_comments)

    columns = [
        "comment_id",
        "comment",
        "likes",
        "published_at",
        "updated_at",
        "reply_count",
        "youtube_order",
    ]
    df = pd.DataFrame(rows, columns=columns)

    return df, metadata
