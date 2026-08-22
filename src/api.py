import asyncio
import os
import time
import datetime as dt

from typing import Any, AsyncGenerator, Optional, Literal, Union

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException

from src.main import run_xactions, RUNNER
from src.items import (
    Tweet,
    ScrapeRequest,
    ScrapeResponse,
    ScrapeTimelineRequest,
    ScrapeTimelineResponse,
)

MAX_CONCURRENT_SCRAPES = int(os.getenv("MAX_CONCURRENT_SCRAPES", "2"))
scrape_gate = asyncio.Semaphore(MAX_CONCURRENT_SCRAPES)

app = FastAPI(
    title="xactions scraping service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


async def _collect(generator) -> list[dict[str, Any]]:
    """ collect an async generator into a list """
    return [item async for item in generator]


def _normalize_stop_date(stop_date: Optional[Union[dt.date, dt.datetime, str]]) -> Optional[dt.date]:
    """
     normalize a date or datetime into an iso yyyy-mm-dd string

     Args:
         stop_date: a date, datetime, or none value received from the request model

     Returns:
         an iso formatted yyyy-mm-dd string or none when no stop date was provided

     Raises:
         HTTPException: if stop_date is not a supported type
    """
    if stop_date is None: return None

    if isinstance(stop_date, str):
        try: return dt.datetime.fromisoformat(stop_date).date()
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail="invalid stop_date, expected iso format date (past not future date)",
            ) from exc

    elif isinstance(stop_date, dt.datetime):
        return stop_date.date()

    elif isinstance(stop_date, dt.date):
        return stop_date

    raise HTTPException(
        status_code=422,
        detail="invalid stop_date, expected iso formate valid date (past not future date)",
    )


async def _stream(websocket: WebSocket, generator: AsyncGenerator[Tweet, None]) -> None:
    """
     stream generator output to a websocket client

     Args:
         websocket: accepted websocket connection used for sending results
         generator: async generator that yields tweet dictionaries
    """
    async for item in generator:
        await websocket.send_json({
            "type": "item",
            "data": item.model_dump_json(ensure_ascii=False, indent=2)
        })

    await websocket.send_json({"type": "done"})


async def _scrape(
    mode: Literal["tweets", "scrape_timeline"],
    target: str,
    limit: int,
    stop_date: Optional[Union[dt.date, dt.datetime, str]],
    auth_token: Optional[str],
    timeout_seconds: int,
) -> AsyncGenerator[Tweet, None]:
    """
    run the xactions scraper through the shared concurrency gate

    Args:
        mode: supported scraper mode, such as tweets or list_timeline
        target: username or timeline url depending on mode
        limit: maximum number of tweets to collect
        stop_date: cutoff date; tweets older than this date are ignored
        auth_token: optional x auth cookie passed into the subprocess environment
        timeout_seconds: maximum number of seconds to wait for output before timing out

    Yields:
        enriched Tweet streamed from the xactions runner

    Raises:
        HTTPException: if the scrape fails inside the downstream runner
    """
    stop_date: dt.date = _normalize_stop_date(stop_date)

    async with scrape_gate:
        async for item in run_xactions(
            mode=mode,
            target=target,
            limit=limit,
            stop_date=stop_date,
            timeout_seconds=timeout_seconds,
            auth_token=auth_token,
        ):
            yield item


@app.get("/health")
async def health() -> dict[str, Any]:
    """ returns the liveness state of the service """
    return {
        "status": "healthy",
        "service": "xactions",
        "version": app.version,
    }


@app.get("/ready")
async def ready() -> dict[str, Any]:
    """ return whether the service is ready to accept requests """
    proc = await asyncio.create_subprocess_exec(
        "node",
        "--version",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )

    await proc.wait()
    node_ready = proc.returncode == 0

    return {
        "status": (
            "ready"
            if RUNNER.is_file() and scrape_gate._value >= 0 and node_ready
            else "not_ready"
        ),
        "node_ready": node_ready,
        "runner": RUNNER.is_file(),
        "available_slots": scrape_gate._value,
        "max_concurrent_scrapes": MAX_CONCURRENT_SCRAPES,
    }


@app.post("/v1/scrape/tweets", response_model=ScrapeResponse)
async def scrape_tweets(req: ScrapeRequest) -> ScrapeResponse:
    """
    scrape tweets from one x account

    Args:
        req: validated scrape request containing the username, limit, timeout, auth token, and stop date

    Returns:
        a structured response containing the username, tweet count, elapsed time, and collected tweets
    """
    started = time.perf_counter()

    tweets = await _collect(
        _scrape(
            mode="tweets",
            target=req.username,
            limit=req.limit,
            stop_date=req.stop_date,
            auth_token=req.auth_token,
            timeout_seconds=req.timeout_seconds,
        )
    )

    elapsed_ms = int((time.perf_counter() - started) * 1000)

    return ScrapeResponse(
        username=req.username,
        limit=req.limit,
        count=len(tweets),
        elapsed_ms=elapsed_ms,
        tweets=tweets,
    )


@app.post("/v1/scrape/timeline", response_model=ScrapeTimelineResponse)
async def scrape_timeline(req: ScrapeTimelineRequest) -> ScrapeTimelineResponse:
    """
    scrape tweets from a timeline url

    Args:
        req: validated timeline request containing the url, limit, timeout, auth token, and stop date

    Returns:
        a structured response containing the url, tweet count, elapsed time, and collected tweets
    """
    started = time.perf_counter()

    tweets = await _collect(
        _scrape(
            mode="scrape_timeline",
            target=req.url,
            limit=req.limit,
            stop_date=req.stop_date,
            auth_token=req.auth_token,
            timeout_seconds=req.timeout_seconds,
        )
    )

    elapsed_ms = int((time.perf_counter() - started) * 1000)

    return ScrapeTimelineResponse(
        url=req.url,
        limit=req.limit,
        count=len(tweets),
        elapsed_ms=elapsed_ms,
        tweets=tweets,
    )


@app.websocket("/v1/ws/tweets")
async def ws_scrape_tweets(websocket: WebSocket) -> None:
    """
     stream tweets from one x account over websocket

     Args:
         websocket: websocket connection used to receive the request payload and send streamed results
    """
    await websocket.accept()

    try:
        payload = await websocket.receive_json()
        req = ScrapeRequest(**payload)

        await _stream(
            websocket,
            _scrape(
                mode="tweets",
                target=req.username,
                limit=req.limit,
                stop_date=req.stop_date,
                auth_token=req.auth_token,
                timeout_seconds=req.timeout_seconds,
            ),
        )
    except WebSocketDisconnect: return
    except Exception as exc:
        await websocket.send_json({"type": "error", "detail": str(exc)})


@app.websocket("/v1/ws/scrape-timeline")
async def ws_scrape_list_timeline(websocket: WebSocket) -> None:
    """
     stream tweets from a timeline url over websocket

     Args:
         websocket: websocket connection used to receive the request payload and send streamed results
    """
    await websocket.accept()

    try:
        payload = await websocket.receive_json()
        req = ScrapeTimelineRequest(**payload)

        await _stream(
            websocket,
            _scrape(
                mode="scrape_timeline",
                target=req.url,
                limit=req.limit,
                stop_date=req.stop_date,
                auth_token=req.auth_token,
                timeout_seconds=req.timeout_seconds,
            ),
        )
    except WebSocketDisconnect: return
    except Exception as exc:
        await websocket.send_json({"type": "error", "detail": str(exc)})
