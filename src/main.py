import asyncio
import hashlib
import json
import os
import re
import datetime as dt

from pathlib import Path
from typing import Any, Optional, AsyncGenerator, Generator, Literal

from fastapi import HTTPException
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from src.items import Tweet

SPACE_RE = re.compile(r"\s+")
CASHTAG_RE = re.compile(r"\$([A-Za-z][A-Za-z0-9_]{0,31})")
HASHTAG_RE = re.compile(r"#([A-Za-z][A-Za-z0-9_]{0,31})")
URL_RE = re.compile(r"https?://[^\s<>\"]+")

APP_DIR = Path(__file__).resolve().parent
RUNNER = APP_DIR / "xactions_runner.mjs"
_sentiment_analyzer = SentimentIntensityAnalyzer()


def _parse_count(value: Any) -> int:
    """ normalize engagement values into integers """
    text: str = str(value or "").strip().replace(",", "")
    if not text:
        return 0

    match: Optional[re.Match[str]] = re.fullmatch(
        r"(\d+(?:\.\d+)?)([KMB])?", text, re.IGNORECASE
    )
    if not match:
        try:
            return max(0, int(float(text)))
        except ValueError:
            return 0

    number: float = float(match.group(1))
    multipliers: dict[str, int] = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    return max(0, round(number * multipliers[(match.group(2) or "").upper()]))


def _enrich_tweet(tweet: dict[str, Any]) -> Tweet:
    """ enrich and normalize a raw tweet returned by xactions """
    body: str = SPACE_RE.sub(" ", str(tweet.get("body") or tweet.get("text") or "")).strip()
    tweet_id: str = str(tweet.get("tweet_id") or tweet.get("id") or "")
    tweet_url: str = str(tweet.get("tweet_url") or tweet.get("url") or "")
    account_name: str = str(tweet.get("account_name") or "")
    username: str = str(tweet.get("username") or "")
    created_at: str = str(tweet.get("time") or tweet.get("timestamp") or "")

    replies: int = _parse_count(tweet.get("replies_count", tweet.get("replies", 0)))
    reposts: int = _parse_count(tweet.get("reposts", tweet.get("retweets", 0)))
    likes: int = _parse_count(tweet.get("likes", 0))
    bookmarks: int = _parse_count(tweet.get("bookmarks", 0))
    views: int = _parse_count(tweet.get("views", 0))

    engagement_count: int = replies + reposts + likes + bookmarks + views
    tweet_weight: int = min(
        5,
        int(
            views / 10_000
            + reposts / 500
            + likes / 1_000
            + replies / 250
            + bookmarks / 250
        ),
    )

    words: list[str] = [word for word in body.split() if len(word) > 3]
    sentiment_score: float = _sentiment_analyzer.polarity_scores(body)["compound"]

    sentiment: str = (
        "positive" if sentiment_score > 0.1
        else "negative" if sentiment_score < -0.1
        else "neutral"
    )

    hashtags: list[str] = sorted({m.group(1) for m in HASHTAG_RE.finditer(body)})
    cashtags: list[str] = sorted({m.group(1).upper() for m in CASHTAG_RE.finditer(body)})
    found_urls: list[str] = sorted({m.group(0) for m in URL_RE.finditer(body)})

    content_hash: str = hashlib.blake2b(
        f"{username}|{created_at}|{body}".encode(),
        digest_size=16,
    ).hexdigest()

    engagement_hash: str = hashlib.blake2b(
        f"{replies}|{reposts}|{likes}|{bookmarks}|{views}".encode(),
        digest_size=16,
    ).hexdigest()

    return Tweet(
        tweet_id=tweet_id,
        tweet_url=tweet_url,
        content_hash=content_hash,
        engagement_hash=engagement_hash,
        account_name=account_name,
        username=username,
        body=body,
        time=created_at,
        sentiment=sentiment,
        verified=bool(tweet.get("verified")),
        has_media=bool(tweet.get("has_media")),
        has_photo=bool(tweet.get("has_photo")),
        has_video=bool(tweet.get("has_video")),
        engagement_count=engagement_count,
        tweet_weight=tweet_weight,
        replies_count=replies,
        reposts=reposts,
        likes=likes,
        bookmarks=bookmarks,
        views=views,
        words_count=len(words),
        words_length=sum(map(len, words)),
        tweet_length=len(body),
        sentiment_score=sentiment_score,
        hashtags=hashtags,
        cashtags=cashtags,
        found_urls=found_urls,
    )


def _parse_output(raw: bytes) -> Generator[Tweet, None, None]:
    """
     parse stdout output from the xactions runner into enriched tweet dictionaries

     Args:
         raw: raw stdout bytes emitted by the node runner

     yields:
         each valid tweet after enrichment

     raises:
         HTTPException: if the output is invalid or cannot be decoded as a json list
    """
    text: str = raw.decode("utf-8", errors="replace").strip()
    try: tweet: dict[str, Any] = json.loads(text) if text else None
    except json.JSONDecodeError as exc: raise HTTPException(status_code=502, detail="invalid response") from exc

    if not isinstance(tweet, dict):
        raise HTTPException(status_code=502, detail=f"invalid response expected dict got: '{tweet}'  -  text: '{text}'")

    yield _enrich_tweet(tweet)


async def _run_xactions(
    mode: str,
    target: str,
    limit: int = 100,
    stop_date: Optional[str] = None,
    auth_token: Optional[str] = None,
    timeout_seconds: int = 120,
) -> AsyncGenerator[Tweet, None]:
    """
     run the xactions node scraper and stream parsed tweet dictionaries

     Args:
         mode: scraper mode passed to the node runner
         target: username or timeline url depending on mode
         limit: maximum number of tweets to collect
         stop_date: optional cutoff date in yyyy-mm-dd format
         auth_token: optional x auth cookie passed into the subprocess environment
         timeout_seconds: maximum number of seconds to wait for output before timing out

     yields:
         enriched tweet dictionaries streamed from stdout as Tweet object

     raises:
         HTTPException: if the input is invalid, the subprocess times out, or the runner fails
    """
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
            line: bytes = await asyncio.wait_for(
                proc.stdout.readline(),
                timeout=timeout_seconds,
            )

            if not line: break
            for tweet in _parse_output(line):
                yield tweet
    except asyncio.TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise HTTPException(status_code=504, detail="scrape timed out") from exc

    stderr: bytes = await proc.stderr.read()
    await proc.wait()
    if proc.returncode != 0:
        raise HTTPException(
            status_code=502,
            detail=stderr.decode("utf-8", errors="replace").strip() or "scrape failed with unkown error",
        )


async def run_xactions(
    mode: Literal["tweets", "scrape_timeline"],
    target: str,
    limit: int,
    stop_date: dt.date,
    timeout_seconds: int,
    auth_token: Optional[str],
) -> AsyncGenerator[Tweet, None]:
    """
     public wrapper around the xactions runner with normalized date handling

     Args:
         mode: supported scraper mode, such as tweets or scrape_timeline
         target: username or timeline url depending on mode
         limit: maximum number of tweets to collect
         stop_date: cutoff date; tweets older than this date are ignored
         timeout_seconds: maximum number of seconds to wait for output before timing out
         auth_token: optional x auth cookie passed into the subprocess environment

     yields:
         enriched Tweet streamed from the internal runner

     raises:
         HTTPException: if stop_date is invalid or the underlying scraper fails
    """
    async for tweet in _run_xactions(
        mode=mode,
        target=target,
        limit=limit,
        stop_date=stop_date.strftime("%Y-%m-%d"),
        auth_token=auth_token,
        timeout_seconds=timeout_seconds,
    ):
        yield tweet
