# xActions Wrapper

A container-first FastAPI microservice for scraping X content through **xActions**.

This project keeps scraping isolated, repeatable, and easy to plug into automation workflows without turning the host machine into a dependency mess. The service exposes a narrow HTTP API around browser-driven scraping, then returns structured JSON that can be consumed by other scripts, pipelines, or downstream analytics.

## What this project does

This app currently exposes 4 HTTP endpoints and 2 Websockets:

- `GET /health`
- `GET /ready`
- `POST /v1/scrape/tweets`
- `POST /v1/scrape/timeline`
- `WS /v1/ws/tweets`
- `WS /v1/ws/scrape-timeline`

The project is intentionally focused. It is not a database, not a queue worker, and not a general analytics platform. It is a microservice whose job is to accept a request, validate it, launch the scraper, and return usable data.

## Why Docker is part of the design

This project depends on more than Python.

The runtime needs:

- Python
- Node.js
- Chromium
- Chrome system libraries
- xActions
- a valid X auth cookie for authenticated pages

Installing all of that directly on the host works until it does not. Packages drift. Browser dependencies break. One project contaminates another. The container avoids that by bundling the entire runtime into one repeatable image.

Docker gives this project four practical advantages:

### Reproducibility
The same image runs the same way on a laptop, a VPS, or a CI machine.

### Isolation
Python, Node, Chromium, and xActions stay inside the container instead of touching the host.

### Deployment simplicity
You build once, then run the container anywhere that supports Docker.

### Failure containment
If the scraper crashes, it crashes inside the container, not on your system.

## The Python environment issue

A common source of confusion in projects like this is not Python itself, but the surrounding environment.

You may run into problems like:

- dependencies installed into one environment, but the app starts with another
- `uv` syncing packages into a different interpreter than the one used at runtime
- `uvicorn` missing even though installation looked successful
- local Python behaving differently from the container Python

That is why this repo is container-first.

The image defines the Python version, the dependencies, the browser stack, and the startup command. That removes most environment drift. If you see a `ModuleNotFoundError`, the first thing to verify is whether the app is running in the same environment where the dependencies were installed.

## Architecture

The project is split into a few small pieces so the code stays readable and maintainable:

- `src/items.py` contains Pydantic request and response models
- `src/api.py` contains the FastAPI routes
- `src/main.py` contains the shared xActions execution helpers
- `src/xactions_runner.mjs` bridges Python to Node/xActions
- `src/__main__.py` starts the API server

That split keeps request validation, endpoint routing, and browser automation from getting tangled together.
## Request flow

The runtime flow is:

1. FastAPI receives the request
2. Pydantic validates the input
3. Python launches the Node runner
4. xActions performs the X scrape
5. Chromium loads the target page when required
6. The Node runner extracts raw tweet data
7. Python parses and normalizes the output
8. The raw tweet is converted into the `Tweet` model
9. Engagement values are normalized
10. Content hashes and engagement hashes are generated
11. Text statistics and sentiment are calculated
12. Hashtags, cashtags, and URLs are extracted
13. The normalized tweet is returned or streamed to the client

## API endpoints

### `GET /health`

A lightweight liveness check.

#### Request

No request body.

#### Response

```json
{
  "status":"healthy",
  "service":"xactions",
  "version":"1.0.0"
}
```

#### Curl

```bash
curl http://localhost:9096/health
```

---

### `GET /ready`

A lightweight readiness check.

#### Request

No request body.

#### Response

```json
{
  "status":"ready",
  "node_ready":true,
  "runner":true,
  "available_slots":2,
  "max_concurrent_scrapes":2
}
```

#### Curl

```bash
curl http://localhost:9096/ready
```

---

### `POST /v1/scrape/tweets`

Scrape tweets from one X account.

The request accepts a single username and processes that account through the shared scraping core.

#### Request body

```json
{
  "username": "elonmusk",
  "limit": 10,
  "timeout_seconds": 120,
  "stop_date": "2026-02-03"
}
```

#### Fields

| Field             | Type | Description                                      |
|-------------------|------|--------------------------------------------------|
| `username`        | str  | X username to scrape                             |
| `limit`           | int  | Maximum number of tweets to fetch                |
| `timeout_seconds` | int  | Maximum time allowed for the scrape              |
| `stop_date`       | date | Optional cutoff date in `YYYY-MM-DD` format      |
| `auth_token`      | str  | Optional X auth cookie passed into the container |

The username is normalized by stripping a leading `@` and validating the remaining handle against the expected X username pattern.

#### Response shape

The tweets endpoint returns the account scrape output produced by the runner, enriched by Python.

```json
{
  "username": "elonmusk",
  "limit": 10,
  "count": 1,
  "elapsed_ms": 18420,
  "tweets": [
    {
      "tweet_id": "2085377974396752305",
      "tweet_url": "https://x.com/elonmusk/status/2085377974396752305",
      "content_hash": "6f0c2e0e5d4c6f2d8d8a9f0b2c2c6a18",
      "engagement_hash": "4c4a4f2dd0c7fdc3bd7ad5e9a16f5d12",
      "account_name": "Elon Musk",
      "username": "elonmusk",
      "body": "Terafab Texas will be the largest and most valuable building on Earth by far.",
      "time": "2026-08-06T14:50:28.000Z",
      "sentiment": "positive",
      "verified": true,
      "has_media": true,
      "has_photo": false,
      "has_video": true,
      "engagement_count": 84874,
      "tweet_weight": 5,
      "replies_count": 5500,
      "reposts": 9400,
      "likes": 74000,
      "bookmarks": 0,
      "views": 10000000,
      "words_count": 12,
      "words_length": 72,
      "tweet_length": 117,
      "sentiment_score": 0.807,
      "hashtags": [],
      "cashtags": [],
      "found_urls": []
    }
  ]
}
```

#### Fields

This endpoint returns the raw X account scrape shape, plus the enrichment fields added by Python.

| Field              | Meaning                                                                  |
|--------------------|--------------------------------------------------------------------------|
| `tweet_id`         | Stable tweet identifier                                                  |
| `tweet_url`        | Permanent URL to the tweet                                               |
| `content_hash`     | BLAKE2b hash derived from the author, timestamp, and normalized body     |
| `engagement_hash`  | BLAKE2b hash derived from reply, repost, like, bookmark, and view counts |
| `account_name`     | Author display name                                                      |
| `username`         | X username without `@`                                                   |
| `body`             | Normalized tweet text                                                    |
| `time`             | Tweet timestamp                                                          |
| `sentiment`        | `positive`, `neutral`, or `negative`                                     |
| `verified`         | Whether the account is detected as verified                              |
| `has_media`        | Whether the tweet contains media                                         |
| `has_photo`        | Whether the tweet contains a photo                                       |
| `has_video`        | Whether the tweet contains a video                                       |
| `engagement_count` | Combined engagement metric                                               |
| `tweet_weight`     | Bounded tweet scoring value                                              |
| `replies_count`    | Number of replies                                                        |
| `reposts`          | Number of reposts                                                        |
| `likes`            | Number of likes                                                          |
| `bookmarks`        | Number of bookmarks                                                      |
| `views`            | Number of views                                                          |
| `words_count`      | Number of words longer than 3 characters                                 |
| `words_length`     | Total character count across those words                                 |
| `tweet_length`     | Total character count of the normalized body                             |
| `sentiment_score`  | VADER compound sentiment score                                           |
| `hashtags`         | Hashtags extracted from the tweet                                        |
| `cashtags`         | Cashtags extracted from the tweet                                        |
| `found_urls`       | URLs extracted from the tweet body                                       |

#### Curl

```bash
curl -X POST http://localhost:9096/v1/scrape/tweets   -H "Content-Type: application/json"   -d '{
    "username": "elonmusk",
    "limit": 10,
    "timeout_seconds": 120,
    "stop_date": "2026-02-03"
  }'
```

---

### `POST /v1/scrape/timeline`

Scrape tweets from any timeline URL.

This endpoint is meant for timeline-style pages, including X list timelines and similar timeline views that can be reached from a URL.

#### Request body

```json
{
  "url": "https://x.com/i/lists/1234567890",
  "limit": 100,
  "timeout_seconds": 120,
  "stop_date": "2026-02-03"
}
```

#### Fields

| Field             | Type | Description                                      |
|-------------------|------|--------------------------------------------------|
| `url`             | str  | Full timeline URL                                |
| `limit`           | int  | Maximum number of timeline items to collect      |
| `timeout_seconds` | int  | Maximum time allowed for the scrape              |
| `stop_date`       | date | Optional cutoff date in `YYYY-MM-DD` format      |
| `auth_token`      | str  | Optional X auth cookie passed into the container |

#### Response shape

The timeline endpoint returns the same normalized `Tweet` object used by the Python enrichment layer.

```json
{
  "url": "https://x.com/i/lists/1234567890",
  "limit": 100,
  "count": 1,
  "elapsed_ms": 31204,
  "tweets": [
    {
      "tweet_id": "1940123456789012345",
      "tweet_url": "https://x.com/Raghavak0nSol/status/1940123456789012345",
      "content_hash": "0c4d8f10d5c3c8c4e6d2f7f1b58a6d22",
      "engagement_hash": "c57e1a7df5bdab6c6f0ef4df6c1e71c7",
      "account_name": "Memecoin Daddy",
      "username": "Raghavak0nSol",
      "body": "3x $VOLE",
      "time": "2026-08-02T09:10:17.000Z",
      "sentiment": "positive",
      "verified": true,
      "has_media": true,
      "has_photo": true,
      "has_video": false,
      "engagement_count": 21025,
      "tweet_weight": 5,
      "replies_count": 79,
      "reposts": 1119,
      "likes": 18594,
      "bookmarks": 1337,
      "views": 0,
      "words_count": 1,
      "words_length": 2,
      "tweet_length": 10,
      "sentiment_score": 0.8123,
      "hashtags": [
        "SOL",
        "VOLE"
      ],
      "cashtags": [
        "VOLE"
      ],
      "found_urls": []
    }
  ]
}
```

#### Curl

```bash
curl -X POST http://localhost:9096/v1/scrape/timeline   -H "Content-Type: application/json"   -d '{
    "url": "https://x.com/i/lists/1234567890",
    "limit": 100,
    "timeout_seconds": 120,
    "stop_date": "2026-02-03"
  }'
```

---

### `WS /v1/ws/tweets`

Stream tweets from one X account.

The WebSocket endpoint returns the normalized `Tweet` model used by the Python processing layer, sending each tweet as soon as it becomes available.

#### Request body

```json
{
  "username": "elonmusk",
  "limit": 10,
  "timeout_seconds": 120,
  "stop_date": "2026-02-03"
}
```

#### Fields

| Field             | Type | Description                                      |
|-------------------|------|--------------------------------------------------|
| `username`        | str  | X username to scrape                             |
| `limit`           | int  | Maximum number of tweets to fetch                |
| `timeout_seconds` | int  | Maximum time allowed for the scrape              |
| `stop_date`       | date | Optional cutoff date in `YYYY-MM-DD` format      |
| `auth_token`      | str  | Optional X auth cookie passed into the container |

#### Streamed Messages

The WebSocket endpoint returns the same tweet shape as `POST /v1/scrape/tweets`, but sends each tweet as soon as it is available.

Each item is streamed like this:

```json
{
  "type": "item",
  "data": {
    "tweet_id": "2085377974396752305",
    "tweet_url": "https://x.com/elonmusk/status/2085377974396752305",
    "content_hash": "6f0c2e0e5d4c6f2d8d8a9f0b2c2c6a18",
    "engagement_hash": "4c4a4f2dd0c7fdc3bd7ad5e9a16f5d12",
    "account_name": "Elon Musk",
    "username": "elonmusk",
    "body": "Terafab Texas will be the largest and most valuable building on Earth by far.",
    "time": "2026-08-06T14:50:28.000Z",
    "sentiment": "positive",
    "verified": true,
    "has_media": true,
    "has_photo": false,
    "has_video": true,
    "engagement_count": 84874,
    "tweet_weight": 5,
    "replies_count": 5500,
    "reposts": 9400,
    "likes": 74000,
    "bookmarks": 0,
    "views": 10000000,
    "words_count": 12,
    "words_length": 72,
    "tweet_length": 117,
    "sentiment_score": 0.807,
    "hashtags": [],
    "cashtags": [],
    "found_urls": []
  }
}
```

When the scrape finishes, the server sends:

```json
{
  "type": "done"
}
```

If an error occurs, the server sends:

```json
{
  "type": "error",
  "detail": "..."
}
```

#### Usage Note

This endpoint is best when you want to process results as they arrive instead of waiting for the full scrape to finish.

## `WS /v1/ws/scrape-timeline`

Stream tweets from any timeline URL.

This WebSocket endpoint works with timeline-style pages, including X list timelines and other timeline views that can be reached from a URL.

### Request Body

```json
{
  "url": "https://x.com/i/lists/1234567890",
  "limit": 100,
  "timeout_seconds": 120,
  "stop_date": "2026-02-03"
}
```

### Fields

| Field             | Type   | Description                                      |
|-------------------|--------|--------------------------------------------------|
| `url`             | `str`  | Full timeline URL                                |
| `limit`           | `int`  | Maximum number of timeline items to collect      |
| `timeout_seconds` | `int`  | Maximum time allowed for the scrape              |
| `stop_date`       | `date` | Optional cutoff date in `YYYY-MM-DD` format      |
| `auth_token`      | `str`  | Optional X auth cookie passed into the container |

### Streamed Messages

The server sends one message per tweet:

```json
{
  "type": "item",
  "data": {
      "tweet_id": "1940123456789012345",
      "tweet_url": "https://x.com/Raghavak0nSol/status/1940123456789012345",
      "content_hash": "0c4d8f10d5c3c8c4e6d2f7f1b58a6d22",
      "engagement_hash": "c57e1a7df5bdab6c6f0ef4df6c1e71c7",
      "account_name": "Memecoin Daddy",
      "username": "Raghavak0nSol",
      "body": "3x $VOLE",
      "time": "2026-08-02T09:10:17.000Z",
      "sentiment": "positive",
      "verified": true,
      "has_media": true,
      "has_photo": true,
      "has_video": false,
      "engagement_count": 21025,
      "tweet_weight": 5,
      "replies_count": 79,
      "reposts": 1119,
      "likes": 18594,
      "bookmarks": 1337,
      "views": 0,
      "words_count": 1,
      "words_length": 2,
      "tweet_length": 10,
      "sentiment_score": 0.8123,
      "hashtags": [
        "SOL",
        "VOLE"
      ],
      "cashtags": [
        "VOLE"
      ],
      "found_urls": []
    }
}
```

When the scrape finishes, the server sends:

```json
{
  "type": "done"
}
```

If an error occurs, the server sends:

```json
{
  "type": "error",
  "detail": "..."
}
```

### Usage Note

This endpoint is the streamed version of the timeline scraper. Use it when the target page is large and you want the data as soon as the browser finds it.

## Output contract

All API and WebSocket scrape results are normalized through the Python `Tweet` model.

The Node/xActions runner may produce different raw structures internally depending on the scrape mode, but the Python processing layer converts those results into the same application-level `Tweet` representation before returning them to clients.

This means consumers of the API should rely on the `Tweet` model rather than the internal xActions response format.

## stop_date

it accepts YYYY-MM-DD
it is normalized in Python
it is applied during scrolling in the browser
it stops once older tweets are reached

The value is validated in Python and normalized before being passed to the Node runner. Inside the browser scraper, tweets are processed from newest to oldest, so the crawl can stop as soon as it reaches tweets older than the cutoff. This avoids unnecessary scrolling and reduces browser work.

That makes `stop_date` useful for:

- faster timeline scraping
- shorter runs
- less DOM processing
- lower response latency
- less wasted time on old content

## Tweet data model

Every scraped tweet is normalized into the `Tweet` Pydantic model before it is returned by the API.

The model contains the original scraped information together with derived fields calculated by the Python processing layer.

### Identity

- `tweet_id`
- `tweet_url`
- `content_hash`

### Author

- `account_name`
- `username`
- `verified`

### Content

- `body`
- `time`
- `hashtags`
- `cashtags`
- `found_urls`

### Media

- `has_media`
- `has_photo`
- `has_video`

### Engagement

- `engagement_count`
- `engagement_hash`
- `replies_count`
- `reposts`
- `likes`
- `bookmarks`
- `views`

### Text analysis

- `words_count`
- `words_length`
- `tweet_length`
- `sentiment_score`
- `sentiment`

### Derived identifiers

#### `content_hash`

The content hash is generated using BLAKE2b from:

```text
username|time|body
```

This gives the application a stable content fingerprint that can be used for duplicate detection or change tracking.

#### `engagement_hash`

The engagement hash is generated independently from:

```text
replies_count|reposts|likes|bookmarks|views
```

This allows downstream systems to detect engagement changes without hashing the entire tweet.

## Engagement normalization

The raw xActions account scraper can return human-readable metrics such as:

```text
74K
9.4K
5.5K
10M
```

The Python enrichment layer normalizes these values into integers:

```json
{
  "likes": 74000,
  "reposts": 9400,
  "replies_count": 5500,
  "views": 10000000
}
```

Supported suffixes are:

- `K`
- `M`
- `B`

Plain numeric values are also accepted.

## Text metrics

### `words_count`

Counts words whose length is greater than three characters.

For:

```text
"this is a very interesting tweet"
```

the words considered are:

```text
this
very
interesting
tweet
```

### `words_length`

The combined character count of the words counted by `words_count`.

### `tweet_length`

The character count of the normalized tweet body.

## Sentiment

VADER is used to calculate the compound sentiment score.

The score is exposed through:

```text
sentiment_score
```

and mapped to:

```text
positive
neutral
negative
```

using the configured thresholds.

## Hashtags, cashtags, and URLs

The Python enrichment layer extracts:

```json
{
  "hashtags": ["SOL", "VOLE"],
  "cashtags": ["VOLE"],
  "found_urls": []
}
```

These fields are normalized into lists so downstream consumers do not need to parse the tweet body again.

## Tweet weight

`tweet_weight` is a derived score based on engagement metrics and capped at `5`.

The current calculation considers:

- views
- reposts
- likes
- replies
- bookmarks

It is intended as a lightweight ranking signal rather than a universal measure of tweet quality.

### Field meanings

| Field              | Meaning                                             |
|--------------------|-----------------------------------------------------|
| `tweet_id`         | Stable tweet identifier                             |
| `tweet_url`        | Permanent tweet URL                                 |
| `content_hash`     | BLAKE2b fingerprint of the normalized tweet content |
| `engagement_hash`  | BLAKE2b fingerprint of the engagement metrics       |
| `account_name`     | Clean display name                                  |
| `username`         | X handle without `@`                                |
| `verified`         | Whether the account is detected as verified         |
| `body`             | Normalized tweet body                               |
| `time`             | Tweet timestamp                                     |
| `hashtags`         | Extracted hashtags                                  |
| `cashtags`         | Extracted cashtags                                  |
| `found_urls`       | URLs found in the tweet                             |
| `has_media`        | Whether the tweet contains media                    |
| `has_photo`        | Whether the tweet contains a photo                  |
| `has_video`        | Whether the tweet contains a video                  |
| `engagement_count` | Combined engagement value                           |
| `tweet_weight`     | Derived tweet score capped at `5`                   |
| `replies_count`    | Normalized reply count                              |
| `reposts`          | Normalized repost count                             |
| `likes`            | Normalized like count                               |
| `bookmarks`        | Normalized bookmark count                           |
| `views`            | Normalized view count                               |
| `words_count`      | Number of words longer than 3 characters            |
| `words_length`     | Total character count of counted words              |
| `tweet_length`     | Total character count of the normalized body        |
| `sentiment_score`  | VADER compound sentiment score                      |
| `sentiment`        | Sentiment label                                     |

This is the data shape that makes the service useful for ranking, scoring, filtering, and downstream analysis.

## Environment variables

The container uses these values:

| Variable                  | Purpose                                     |
|---------------------------|---------------------------------------------|
| `XACTIONS_AUTH_TOKEN`     | X auth cookie passed into the container     |
| `XACTIONS_SESSION_COOKIE` | Optional alias for the same value           |
| `MAX_CONCURRENT_SCRAPES`  | Limits how many scrape jobs can run at once |
| `DEFAULT_TIMEOUT_SECONDS` | Default timeout for scrape requests         |
| `HOST`                    | Host to bind to                             |
| `PORT`                    | Port to listen on, defaults to `9096`       |

## Docker setup

### 1. Create your `.env`

Put this next to `docker-compose.yml`:

```env
XACTIONS_AUTH_TOKEN=your_x_auth_cookie_here
HOST=0.0.0.0
PORT=9096
```

Do not hardcode the cookie into the image.

### 2. Build and start the service

```bash
docker compose up -d --build
```
or in case of having some trouble after some successful builds
```bash
docker compose build --no-cache
```

### 3. Verify the health endpoint

```bash
curl http://localhost:9096/health
```

Expected response:

```json
{
  "status":"healthy",
  "service":"xactions",
  "version":"1.0.0"
}
```

### 4. Verify the readiness endpoint

```bash
curl http://localhost:9096/ready
```

Expected response:

```json
{
  "status":"ready",
  "node_ready":true,
  "runner":true,
  "available_slots":2,
  "max_concurrent_scrapes":2
}
```

or if something is wrong

```json
{
  "status":"not-ready",
  "node_ready":true,
  "runner":true,
  "available_slots":0,
  "max_concurrent_scrapes":2
}
```

## Running locally with `uv`

Docker is the recommended path, but local development is still possible if your environment is already aligned.

Typical local flow:

```bash
uv sync
uv run python -m src
```

If the local runtime becomes inconsistent, use Docker instead. That is the safer and more repeatable route for this project.

## Why this is a microservice

This project has one job and does it behind a small API.

It does not try to own:

- storage
- dashboards
- analytics pipelines
- queue management
- long-term state
- user accounts
- orchestration

That makes it a microservice in the practical sense:

- small surface area
- easy to deploy independently
- easy to swap or upgrade
- easy to call from other tools
- easy to keep focused

That design is useful when you want scraping as a building block instead of a giant application.

## Troubleshooting

### `ModuleNotFoundError: uvicorn`

This usually means the app is starting in a Python environment that does not contain the installed dependencies.

Check that:

- `uvicorn` is present in `pyproject.toml`
- the image was rebuilt after dependency changes
- the runtime interpreter matches the environment used to install packages

### `ERR_MODULE_NOT_FOUND: Cannot find package 'xactions'`

This usually means the Node runner cannot resolve the package in its current module path.

Inside the container, xActions should be installed in a way that Node can import it from the project runtime. If the package was only installed globally, the ESM import may fail.

### Empty tweet output

If the endpoint returns an empty array, likely causes are:

- the page did not expose tweet cards
- the target account is private or inaccessible
- the cookie is missing
- the timeline URL is incorrect
- the browser session needs a refresh

### Chromium launch errors

If Chromium refuses to start, check:

- missing shared libraries
- sandbox restrictions
- wrong executable path
- incomplete browser installation

### Invalid `stop_date`

`stop_date` must be a real calendar date in `YYYY-MM-DD` format.

Examples:

- `2026-02-03` is valid
- `2026-02-30` is invalid
- `2026-2-3` is invalid

## Design goals

The project is built to stay small and readable.

The goal is not to hide the logic behind abstractions that make debugging harder.

The goal is to keep each layer obvious:

- validation
- execution
- browser automation
- JSON response
- enrichment

That makes the service easier to extend later without turning it into a mess.

## Future ideas

The next work should focus on making the scraper more consistent, more resilient, and more useful downstream.

Possible next steps:

- normalize the output contract across REST and WebSocket endpoints so each route is documented exactly as it behaves
- expand tweet extraction with more structured fields, especially:
  - mentions
  - quote tweet metadata
  - retweet metadata
  - reply metadata
  - author profile details
  - media details
  - edit markers when available
- improve scraping reliability when X changes its DOM structure
- add stronger fallback logic for account pages, list timelines, and partial page loads
- improve handling for login walls, soft blocks, and rate-limited pages
- add cursor-based continuation so long scrapes can resume cleanly
- add caching and deduplication for repeated timeline requests
- add request tracing so every scrape can be debugged from start to finish
- add structured logs and metrics for scrape quality, timing, failures, and empty results
- add retries with backoff for transient browser and network failures
- add contract tests that verify the response schema for every endpoint
- add more endpoint coverage for other X timeline patterns when needed
- add optional export targets for downstream pipelines and analytics jobs
- support richer enrichment later, such as better sentiment, author scoring, and narrative detection

The overall goal is to keep the service small, but make the scraping output more complete and more reliable each time it is extended.

## Final note

This project is a scraper service, not a platform.

That is the point.

It stays focused, containerized, and easy to plug into whatever you build next.
