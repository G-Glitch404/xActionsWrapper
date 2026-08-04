import os
import re

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

DEFAULT_TIMEOUT_SECONDS = int(os.getenv("DEFAULT_TIMEOUT_SECONDS", "120"))
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")


class ScrapeRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    limit: int = Field(default=10, ge=1, le=100)
    auth_token: str | None = Field(default=None, min_length=1, max_length=512)
    timeout_seconds: int = Field(default=DEFAULT_TIMEOUT_SECONDS, ge=10, le=600)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        value: str = value.strip().lstrip("@")
        if not USERNAME_RE.fullmatch(value):
            raise ValueError("invalid username")
        return value


class ListTimelineRequest(BaseModel):
    list_url: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=100, ge=1, le=1000)
    auth_token: Optional[str] = Field(default=None, min_length=1, max_length=512)
    timeout_seconds: int = Field(default=DEFAULT_TIMEOUT_SECONDS, ge=10, le=600)

    @field_validator("list_url")
    @classmethod
    def normalize_list_url(cls, value: str) -> str:
        value: str = value.strip()
        if not value:
            raise ValueError("list_url cannot be empty")
        return value


class ScrapeResponse(BaseModel):
    username: str
    limit: int
    count: int
    elapsed_ms: int
    tweets: list[dict[str, Any]]


class ListTimelineResponse(BaseModel):
    list_url: str
    limit: int
    count: int
    elapsed_ms: int
    tweets: list[dict[str, Any]]
