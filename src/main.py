import asyncio
import json
import os

from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException

APP_DIR = Path(__file__).resolve().parent
RUNNER = APP_DIR / "xactions_runner.mjs"


async def _run_xactions(
    mode: str,
    target: str,
    limit: int,
    auth_token: Optional[str],
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    env = os.environ.copy()

    if auth_token:
        env["XACTIONS_AUTH_TOKEN"] = auth_token
        env["XACTIONS_SESSION_COOKIE"] = auth_token

    proc = await asyncio.create_subprocess_exec(
        "node",
        str(RUNNER),
        mode,
        target,
        str(limit),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(APP_DIR.parent),
        env=env,
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

    try:
        data = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="invalid response")

    if not isinstance(data, list):
        raise HTTPException(status_code=502, detail="invalid response")

    return data


async def run_xactions_tweets(
    username: str,
    limit: int,
    auth_token: Optional[str],
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    return await _run_xactions(
        mode="tweets",
        target=username,
        limit=limit,
        auth_token=auth_token,
        timeout_seconds=timeout_seconds,
    )


async def run_xactions_list_timeline(
    list_url: str,
    limit: int,
    auth_token: Optional[str],
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    return await _run_xactions(
        mode="list_timeline",
        target=list_url,
        limit=limit,
        auth_token=auth_token,
        timeout_seconds=timeout_seconds,
    )
