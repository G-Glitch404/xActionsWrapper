import os
import re
import datetime as dt

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

DEFAULT_TIMEOUT_SECONDS = int(os.getenv("DEFAULT_TIMEOUT_SECONDS", "120"))
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")


class ScrapeRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    limit: int = Field(default=10, ge=1, le=100)
    auth_token: Optional[str] = Field(default=None, min_length=1, max_length=512)
    timeout_seconds: int = Field(default=DEFAULT_TIMEOUT_SECONDS, ge=10, le=600)
    stop_date: Optional[dt.date] = None

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        """ ensures username is valid """
        value: str = value.strip().lstrip("@")
        if not USERNAME_RE.fullmatch(value):
            raise ValueError("invalid username")
        return value


class ListTimelineRequest(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=100, ge=1, le=1000)
    auth_token: Optional[str] = Field(default=None, min_length=1, max_length=512)
    timeout_seconds: int = Field(default=DEFAULT_TIMEOUT_SECONDS, ge=10, le=600)
    stop_date: Optional[dt.date] = None

    @field_validator("url")
    @classmethod
    def normalize_url(cls, value: str) -> str:
        """ ensures url is valid """
        value: str = value.strip()
        if not value:
            raise ValueError("url cannot be empty")
        return value


class ScrapeResponse(BaseModel):
    username: str
    limit: int
    count: int
    elapsed_ms: int
    tweets: list[dict[str, Any]]


class ListTimelineResponse(BaseModel):
    url: str
    limit: int
    count: int
    elapsed_ms: int
    tweets: list[dict[str, Any]]
