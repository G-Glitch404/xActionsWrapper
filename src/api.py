import asyncio
import os
import time

from fastapi import FastAPI

from src.main import run_xactions_tweets, run_xactions_list_timeline
from src.items import ListTimelineRequest, ScrapeRequest, ListTimelineResponse, ScrapeResponse

MAX_CONCURRENT_SCRAPES = int(os.getenv("MAX_CONCURRENT_SCRAPES", "2"))
scrape_gate = asyncio.Semaphore(MAX_CONCURRENT_SCRAPES)

app = FastAPI(
    title="xactions scraping service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/v1/scrape/list-timeline", response_model=ListTimelineResponse)
async def scrape_list_timeline(req: ListTimelineRequest) -> ListTimelineResponse:
    started = time.perf_counter()

    async with scrape_gate:
        tweets = await run_xactions_list_timeline(
            list_url=req.list_url,
            limit=req.limit,
            auth_token=req.auth_token,
            timeout_seconds=req.timeout_seconds,
        )

    elapsed_ms = int((time.perf_counter() - started) * 1000)

    return ListTimelineResponse(
        list_url=req.list_url,
        limit=req.limit,
        count=len(tweets),
        elapsed_ms=elapsed_ms,
        tweets=tweets,
    )


@app.post("/v1/scrape/tweets", response_model=ScrapeResponse)
async def scrape_tweets(req: ScrapeRequest) -> ScrapeResponse:
    started: float = time.perf_counter()

    async with scrape_gate:
        tweets = await run_xactions_tweets(
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
