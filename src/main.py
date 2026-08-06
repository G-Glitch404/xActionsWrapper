import asyncio
import json
import os
import datetime as dt

from pathlib import Path
from typing import Any, Optional, AsyncGenerator, Generator, Literal

from fastapi import HTTPException
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

APP_DIR = Path(__file__).resolve().parent
RUNNER = APP_DIR / "xactions_runner.mjs"
_sentiment_analyzer = SentimentIntensityAnalyzer()


def _enrich_tweet(tweet: dict[str, Any]) -> dict[str, Any]:
    text: str = str(tweet.get("text") or tweet.get("body") or "")
    words_count: int = sum(1 for word in text.split() if len(word) > 3)
    sentiment_score: float = _sentiment_analyzer.polarity_scores(text)["compound"]

    tweet["words_count"] = words_count
    tweet["sentiment_score"] = sentiment_score

    if sentiment_score > 0.1: tweet["sentiment"] = "positive"
    elif sentiment_score < -0.1: tweet["sentiment"] = "negative"
    else: tweet["sentiment"] = "neutral"

    return tweet


def _parse_output(raw: bytes) -> Generator[dict[str, Any]]:
    text: str = raw.decode("utf-8", errors="replace").strip()
    try: data: Any = json.loads(text) if text else []
    except json.JSONDecodeError as exc: raise HTTPException(status_code=502, detail="invalid response") from exc

    if not isinstance(data, list):
        raise HTTPException(status_code=502, detail="invalid response")

    for tweet in data:
        if not isinstance(tweet, dict): continue
        yield _enrich_tweet(tweet)


async def _run_xactions(
    mode: str,
    target: str,
    limit: int = 100,
    stop_date: Optional[str] = None,
    auth_token: Optional[str] = None,
    timeout_seconds: int = 120,
) -> AsyncGenerator[dict[str, Any], None]:
    """  """
    if stop_date and not isinstance(stop_date, str):
        raise HTTPException(
            status_code=422,
            detail="invalid stop_date, expected format: YYYY-MM-DD",
        )

    env: dict[str, str] = os.environ.copy()

    if auth_token:
        env["XACTIONS_AUTH_TOKEN"] = auth_token
        env["XACTIONS_SESSION_COOKIE"] = auth_token

    proc = await asyncio.create_subprocess_exec(
        "node",
        str(RUNNER),
        mode,
        target,
        str(limit),
        stop_date,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(APP_DIR.parent),
        env=env,
    )

    try:
        while True:
            line = await asyncio.wait_for(
                proc.stdout.readline(),
                timeout=timeout_seconds,
            )

            if not line: break
            for tweet in _parse_output(line):
                yield _enrich_tweet(tweet)
    except asyncio.TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise HTTPException(status_code=504, detail="scrape timed out") from exc

    stderr = await proc.stderr.read()
    await proc.wait()
    if proc.returncode != 0:
        raise HTTPException(
            status_code=502,
            detail=stderr.decode("utf-8", errors="replace").strip() or "scrape failed",
        )


async def run_xactions(
    mode: Literal["tweets", "scrape_timeline"],
    target: str,
    limit: int,
    stop_date: dt.datetime,
    timeout_seconds: int,
    auth_token: Optional[str],
) -> AsyncGenerator[dict[str, Any], None]:
    async for tweet in _run_xactions(
        mode=mode,
        target=target,
        limit=limit,
        stop_date=stop_date.date().strftime("YYYY-MM-DD"),
        auth_token=auth_token,
        timeout_seconds=timeout_seconds,
    ):
        yield tweet
