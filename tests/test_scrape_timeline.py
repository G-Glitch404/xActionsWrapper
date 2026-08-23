import asyncio
import json
import os

import httpx
import pytest
import websockets

from typing import Any, Optional

HTTP_BASE_URL = os.getenv("CRAWLER_BASE_URL", "http://localhost:9096").rstrip("/")
WS_BASE_URL = HTTP_BASE_URL.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
WS_PATH = "/v1/ws/scrape-timeline"

TEST_URL = os.getenv("TEST_X_TIMELINE_URL")
TEST_LIMIT = int(os.getenv("TEST_CRAWL_LIMIT", "100"))
TEST_STOP_DATE = os.getenv("TEST_STOP_DATE")
HTTP_TIMEOUT = float(os.getenv("TEST_REQUEST_TIMEOUT", "120"))
WS_TIMEOUT = float(os.getenv("TEST_WS_TIMEOUT", "120"))


def _check_readiness() -> dict[str, Any]:
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        response = client.get(f"{HTTP_BASE_URL}/ready")

    assert response.status_code == 200, (
        f"/ready returned HTTP {response.status_code}: {response.text}"
    )

    data = response.json()
    assert isinstance(data, dict)

    for field in (
        "status",
        "node_ready",
        "runner",
        "available_slots",
        "max_concurrent_scrapes",
    ):
        assert field in data, f"/ready response is missing {field!r}"

    return data


@pytest.fixture(scope="session")
def websocket_ready():
    try: readiness: dict[str, Any] = _check_readiness()
    except httpx.HTTPError as exc:
        pytest.fail(f"Could not reach xActionsWrapper at {HTTP_BASE_URL}: {exc}")

    if readiness["status"] != "ready":
        pytest.skip(f"xActionsWrapper is reachable but not ready: {readiness}")

    if readiness["node_ready"] is not True:
        pytest.skip(f"Node.js is not ready: {readiness}")

    if readiness["runner"] is not True:
        pytest.skip(f"xActions runner is unavailable: {readiness}")

    if int(readiness["available_slots"]) < 1:
        pytest.skip(f"xActionsWrapper has no available scrape slots: {readiness}")

    return readiness


def _payload() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "url": TEST_URL,
        "limit": TEST_LIMIT,
    }

    if TEST_STOP_DATE:
        payload["stop_date"] = TEST_STOP_DATE

    return payload


@pytest.mark.skipif(
    not TEST_URL,
    reason="Set TEST_X_TIMELINE_URL to run the WebSocket timeline integration test.",
)
def test_scrape_timeline_websocket(websocket_ready) -> None:
    async def run() -> None:
        tweets: list[dict[str, Any]] = []
        done_seen = False

        async with websockets.connect(
            f"{WS_BASE_URL}{WS_PATH}",
            open_timeout=WS_TIMEOUT,
            close_timeout=WS_TIMEOUT,
            ping_timeout=WS_TIMEOUT,
            max_size=4 * 1024 * 1024,
        ) as websocket:
            await websocket.send(json.dumps(_payload()))

            while True:
                raw = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=WS_TIMEOUT,
                )

                assert isinstance(raw, str), "Expected text JSON WebSocket messages"

                event = json.loads(raw)

                assert isinstance(event, dict)
                assert "type" in event

                event_type = event["type"]

                if event_type == "item":
                    tweet: Optional[dict[str, Any]] = event.get("data")

                    assert isinstance(tweet, dict)
                    assert isinstance(tweet.get("tweet_id"), str)
                    assert tweet["tweet_id"]
                    assert isinstance(tweet.get("tweet_url"), str)
                    assert tweet["tweet_url"].startswith("https://x.com/")
                    assert isinstance(tweet.get("account_name"), str)
                    assert isinstance(tweet.get("username"), str)
                    assert isinstance(tweet.get("body"), str)
                    assert isinstance(tweet.get("time"), str)
                    assert isinstance(tweet.get("verified"), bool)
                    assert isinstance(tweet.get("has_media"), bool)
                    assert isinstance(tweet.get("has_photo"), bool)
                    assert isinstance(tweet.get("has_video"), bool)
                    assert isinstance(tweet.get("engagement_count"), int)
                    assert isinstance(tweet.get("tweet_weight"), int)
                    assert isinstance(tweet.get("replies_count"), int)
                    assert isinstance(tweet.get("reposts"), int)
                    assert isinstance(tweet.get("likes"), int)
                    assert isinstance(tweet.get("bookmarks"), int)
                    assert isinstance(tweet.get("views"), int)
                    assert isinstance(tweet.get("words_count"), int)
                    assert isinstance(tweet.get("words_length"), int)
                    assert isinstance(tweet.get("tweet_length"), int)
                    assert isinstance(tweet.get("sentiment_score"), float)
                    assert tweet.get("sentiment") in {
                        "positive",
                        "neutral",
                        "negative",
                    }
                    assert isinstance(tweet.get("hashtags"), list)
                    assert isinstance(tweet.get("cashtags"), list)
                    assert isinstance(tweet.get("found_urls"), list)
                    assert isinstance(tweet.get("content_hash"), str)
                    assert tweet["content_hash"]
                    assert isinstance(tweet.get("engagement_hash"), str)
                    assert tweet["engagement_hash"]

                    tweets.append(tweet)

                    assert len(tweets) <= TEST_LIMIT

                elif event_type == "done":
                    done_seen = True
                    break

                elif event_type == "error":
                    pytest.fail(
                        f"xActionsWrapper WebSocket error: "
                        f"{event.get('detail', 'Unknown error')}"
                    )

                else:
                    pytest.fail(
                        f"Unexpected WebSocket event type: {event_type!r}"
                    )

        assert done_seen is True
        assert len(tweets) <= TEST_LIMIT

        if tweets:
            assert len({tweet["tweet_id"] for tweet in tweets}) == len(tweets)

    asyncio.run(run())
