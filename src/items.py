import os
import re
import datetime as dt

from urllib.parse import parse_qs, urlsplit
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

DEFAULT_TIMEOUT_SECONDS: int = int(os.getenv("DEFAULT_TIMEOUT_SECONDS", "120"))
USERNAME_RE: Any = re.compile(r"^[A-Za-z0-9_]{1,15}$")


class ScrapeRequest(BaseModel):
    username: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=10_000)
    auth_token: Optional[str] = Field(default=None, min_length=1, max_length=512)
    timeout_seconds: int = Field(default=DEFAULT_TIMEOUT_SECONDS, ge=10, le=601)
    stop_date: Optional[dt.date] = None

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        """ ensures username is valid """
        value: str = value.strip().lstrip("@")
        if not USERNAME_RE.fullmatch(value):
            raise ValueError("invalid username")
        return value


class ScrapeTimelineRequest(BaseModel):
    url: str = Field(min_length=1, max_length=1024)
    limit: int = Field(default=100, ge=1, le=10_000)
    auth_token: Optional[str] = Field(default=None, min_length=1, max_length=128)
    timeout_seconds: int = Field(default=DEFAULT_TIMEOUT_SECONDS, ge=10, le=600)
    stop_date: Optional[dt.date] = None

    @field_validator("url")
    @classmethod
    def normalize_url(cls, value: str) -> str:
        """ validate and normalize supported x.com timeline urls """
        value: str = value.strip()
        if not value:
            raise ValueError("url cannot be empty")

        parsed: Any = urlsplit(value)

        if parsed.scheme != "https" or parsed.hostname != "x.com":
            raise ValueError("only https://x.com URLs are supported")

        if parsed.username or parsed.password or parsed.port:
            raise ValueError("invalid x.com URL")

        path: str = parsed.path.rstrip("/")

        if re.fullmatch(r"/search", path):
            query = parse_qs(parsed.query)
            if not query.get("q", [""])[0].strip():
                raise ValueError("search URL must contain a non-empty q parameter")
            return value

        if re.fullmatch(r"/i/lists/\d+", path):
            return value

        if re.fullmatch(r"/[A-Za-z0-9_]{1,15}", path):
            return value

        raise ValueError("unsupported x.com URL; expected a search, list, or profile URL")


class Tweet(BaseModel):
    tweet_id: str
    tweet_url: str
    content_hash: str
    engagement_hash: str
    account_name: str
    username: str
    body: str
    time: str
    sentiment: str
    verified: bool
    has_media: bool
    has_photo: bool
    has_video: bool
    engagement_count: int
    tweet_weight: int
    replies_count: int
    reposts: int
    likes: int
    bookmarks: int
    views: int
    words_count: int
    words_length: int
    tweet_length: int
    sentiment_score: float
    hashtags: list[str]
    cashtags: list[str]
    found_urls: list[str]


class ScrapeResponse(BaseModel):
    username: str
    limit: int
    count: int
    elapsed_ms: int
    tweets: list[Tweet]


class ScrapeTimelineResponse(BaseModel):
    url: str
    limit: int
    count: int
    elapsed_ms: int
    tweets: list[Tweet]
