import asyncio
import json
import os
import re
import time

from pathlib import Path
from typing import Any, Optional


from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

load_dotenv()

APP_DIR = Path(__file__).resolve().parent
RUNNER = APP_DIR / "xactions_runner.mjs"
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")

MAX_CONCURRENT_SCRAPES = int(os.getenv("MAX_CONCURRENT_SCRAPES", "2"))
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("DEFAULT_TIMEOUT_SECONDS", "120"))

scrape_gate = asyncio.Semaphore(MAX_CONCURRENT_SCRAPES)

app = FastAPI(
    title="xactions scraping service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


class ScrapeRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    limit: int = Field(default=10, ge=1, le=100)
    auth_token: str | None = Field(default=None, min_length=1, max_length=512)
    timeout_seconds: int = Field(default=DEFAULT_TIMEOUT_SECONDS, ge=10, le=600)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        value = value.strip().lstrip("@")
        if not USERNAME_RE.fullmatch(value):
            raise ValueError("invalid username")
        return value


class ScrapeResponse(BaseModel):
    username: str
    limit: int
    count: int
    elapsed_ms: int
    tweets: list[dict[str, Any]]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}


async def run_xactions(
        username: str,
        limit: int,
        auth_token: Optional[str],
        timeout_seconds: int
) -> list[dict[str, Any]]:
    if auth_token:
        os.environ["X_AUTH_TOKEN"] = auth_token

    proc = await asyncio.create_subprocess_exec(
        "node",
        str(RUNNER),
        username,
        str(limit),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(APP_DIR.parent),
        env=os.environ,
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise HTTPException(status_code=504, detail="scrape timed out")

    if proc.returncode != 0:
        message = stderr.decode("utf-8", errors="replace").strip() or "scrape failed"
        raise HTTPException(status_code=502, detail=message)

    raw = stdout.decode("utf-8", errors="replace").strip()
    try: data = json.loads(raw) if raw else []
    except json.JSONDecodeError: raise HTTPException(status_code=502, detail="invalid response")

    if not isinstance(data, list):
        raise HTTPException(status_code=502, detail="invalid response")

    return data


@app.post("/v1/scrape/tweets", response_model=ScrapeResponse)
async def scrape_tweets(req: ScrapeRequest) -> ScrapeResponse:
    started: float = time.perf_counter()

    async with scrape_gate:
        tweets = await run_xactions(
            username=req.username,
            limit=req.limit,
            auth_token=req.auth_token,
            timeout_seconds=req.timeout_seconds,
        )

    elapsed_ms: int = int((time.perf_counter() - started) * 1000)

    return ScrapeResponse(
        username=req.username,
        limit=req.limit,
        count=len(tweets),
        elapsed_ms=elapsed_ms,
        tweets=tweets,
    )
