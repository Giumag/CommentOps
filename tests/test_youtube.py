import pytest

from src.youtube import (
    YouTubeAPIError,
    _dedupe_interleaved,
    extract_video_id,
    fetch_youtube_video,
)


VIDEO_ID = "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "value",
    [
        VIDEO_ID,
        f"https://www.youtube.com/watch?v={VIDEO_ID}",
        f"https://youtube.com/watch?v={VIDEO_ID}&t=10",
        f"https://youtu.be/{VIDEO_ID}",
        f"https://www.youtube.com/shorts/{VIDEO_ID}",
        f"https://www.youtube.com/embed/{VIDEO_ID}",
        f"https://www.youtube.com/live/{VIDEO_ID}",
    ],
)
def test_extract_video_id_supported_shapes(value):
    assert extract_video_id(value) == VIDEO_ID


def test_extract_video_id_rejects_invalid_url():
    with pytest.raises(ValueError):
        extract_video_id("https://example.com/not-youtube")


def test_dedupe_interleaved_preserves_both_views():
    left = [
        {"comment_id": "a"},
        {"comment_id": "b"},
        {"comment_id": "c"},
    ]
    right = [
        {"comment_id": "b"},
        {"comment_id": "d"},
        {"comment_id": "e"},
    ]

    result = _dedupe_interleaved(left, right, 5)
    assert [item["comment_id"] for item in result] == ["a", "b", "d", "c", "e"]


def test_fetch_balanced_comments_and_metadata():
    def fake_request(resource, params, api_key):
        assert api_key == "test-key"

        if resource == "videos":
            return {
                "items": [
                    {
                        "id": VIDEO_ID,
                        "snippet": {
                            "title": "Demo video",
                            "channelTitle": "Demo channel",
                            "publishedAt": "2026-01-01T00:00:00Z",
                        },
                        "statistics": {"commentCount": "4"},
                    }
                ]
            }

        order = params["order"]
        items = {
            "relevance": [
                {
                    "snippet": {
                        "totalReplyCount": 2,
                        "topLevelComment": {
                            "id": "a",
                            "snippet": {
                                "textOriginal": "Top comment",
                                "likeCount": 10,
                                "publishedAt": "2026-01-02T00:00:00Z",
                                "updatedAt": "2026-01-02T00:00:00Z",
                            },
                        },
                    }
                },
                {
                    "snippet": {
                        "totalReplyCount": 0,
                        "topLevelComment": {
                            "id": "b",
                            "snippet": {
                                "textOriginal": "Shared comment",
                                "likeCount": 5,
                                "publishedAt": "2026-01-03T00:00:00Z",
                                "updatedAt": "2026-01-03T00:00:00Z",
                            },
                        },
                    }
                },
            ],
            "time": [
                {
                    "snippet": {
                        "totalReplyCount": 0,
                        "topLevelComment": {
                            "id": "b",
                            "snippet": {
                                "textOriginal": "Shared comment",
                                "likeCount": 5,
                                "publishedAt": "2026-01-03T00:00:00Z",
                                "updatedAt": "2026-01-03T00:00:00Z",
                            },
                        },
                    }
                },
                {
                    "snippet": {
                        "totalReplyCount": 1,
                        "topLevelComment": {
                            "id": "c",
                            "snippet": {
                                "textOriginal": "Recent comment",
                                "likeCount": 1,
                                "publishedAt": "2026-01-04T00:00:00Z",
                                "updatedAt": "2026-01-04T00:00:00Z",
                            },
                        },
                    }
                },
            ],
        }

        return {"items": items[order]}

    df, metadata = fetch_youtube_video(
        VIDEO_ID,
        "test-key",
        max_comments=3,
        sampling="balanced",
        request_json=fake_request,
    )

    assert metadata.title == "Demo video"
    assert metadata.channel_title == "Demo channel"
    assert metadata.public_comment_count == 4
    assert list(df["comment_id"]) == ["a", "b", "c"]
    assert list(df["likes"]) == [10, 5, 1]


def test_video_not_found_is_explicit():
    def fake_request(resource, params, api_key):
        if resource == "videos":
            return {"items": []}
        raise AssertionError("comments should not be requested")

    with pytest.raises(YouTubeAPIError) as exc:
        fetch_youtube_video(
            VIDEO_ID,
            "test-key",
            request_json=fake_request,
        )

    assert exc.value.reason == "videoNotFound"
