# xActions Wrapper

A container-first FastAPI microservice for scraping X content through **xActions**.

This project keeps scraping isolated, repeatable, and easy to plug into automation workflows without turning the host machine into a dependency mess. The service exposes a narrow HTTP API around browser-driven scraping, then returns structured JSON that can be consumed by other scripts, pipelines, or downstream analytics.

## What this project does

This app currently exposes four HTTP endpoints:

- `GET /health`
- `GET /ready`
- `POST /v1/scrape/tweets`
- `POST /v1/scrape/list-timeline`

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

The runtime flow is intentionally simple:

1. FastAPI receives the request
2. Pydantic validates the input
3. Python launches the Node runner
4. the runner starts xActions
5. Chromium loads the page
6. the scraper extracts data from the DOM
7. xActions returns JSON
8. Python enriches the tweet data
9. Python returns the response to the client

This keeps the scraping logic hidden behind a clean HTTP boundary.

## API endpoints

### `GET /health`

A lightweight liveness check.

#### Request

No request body.

#### Response

```json
{
  "status": "ok"
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
  "status": "ready"
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

```json
{
  "username": "elonmusk",
  "limit": 10,
  "count": 10,
  "elapsed_ms": 18420,
  "tweets": [
    {
      "tweet_id": "1940123456789012345",
      "tweet_url": "https://x.com/user/status/1940123456789012345",
      "account_name": "Memecoin Daddy",
      "username": "Raghavak0nSol",
      "verified": true,
      "body": "3x $VOLE ...",
      "time": "2026-08-02T09:10:17.000Z",
      "hashtags": [
        "SOL",
        "VOLE"
      ],
      "has_media": true,
      "has_photo": true,
      "has_video": false,
      "replies": 79,
      "reposts": 1119,
      "likes": 18594,
      "bookmarks": 1337,
      "views": 645918,
      "words_count": 4,
      "sentiment_score": 0.8123,
      "sentiment": "positive"
    }
  ]
}
```

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

### `POST /v1/scrape/list-timeline`

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

```json
{
  "url": "https://x.com/i/lists/1234567890",
  "limit": 100,
  "count": 100,
  "elapsed_ms": 31204,
  "tweets": [
    {
      "tweet_id": "1940123456789012345",
      "tweet_url": "https://x.com/user/status/1940123456789012345",
      "account_name": "Memecoin Daddy",
      "username": "Raghavak0nSol",
      "verified": true,
      "body": "3x $VOLE ...",
      "time": "2026-08-02T09:10:17.000Z",
      "hashtags": [
        "SOL",
        "VOLE"
      ],
      "has_media": true,
      "has_photo": true,
      "has_video": false,
      "replies": 79,
      "reposts": 1119,
      "likes": 18594,
      "bookmarks": 1337,
      "views": 645918,
      "words_count": 4,
      "sentiment_score": 0.8123,
      "sentiment": "positive"
    }
  ]
}
```

#### Curl

```bash
curl -X POST http://localhost:9096/v1/scrape/list-timeline   -H "Content-Type: application/json"   -d '{
    "url": "https://x.com/i/lists/1234567890",
    "limit": 100,
    "timeout_seconds": 120,
    "stop_date": "2026-02-03"
  }'
```

## stop_date

`stop_date` accepts `YYYY-MM-DD`.

The value is validated in Python and normalized before being passed to the Node runner. Inside the browser scraper, tweets are processed from newest to oldest, so the crawl can stop as soon as it reaches tweets older than the cutoff. This avoids unnecessary scrolling and reduces browser work.

That makes `stop_date` useful for:

- faster timeline scraping
- shorter runs
- less DOM processing
- lower response latency
- less wasted time on old content

## Extracted tweet data

The scraper returns richer tweet objects than the old version.

A typical extracted item can include:

- `tweet_id`
- `tweet_url`
- `account_name`
- `username`
- `verified`
- `body`
- `time`
- `hashtags`
- `has_media`
- `has_photo`
- `has_video`
- `replies`
- `reposts`
- `likes`
- `bookmarks`
- `views`

Python additionally enriches every tweet with:

- `words_count`
- `sentiment_score`
- `sentiment`

### Field meanings

| Field             | Meaning                                                  |
|-------------------|----------------------------------------------------------|
| `tweet_id`        | Stable tweet identifier extracted from the status URL    |
| `tweet_url`       | Permanent link to the tweet                              |
| `account_name`    | Clean display name from the author line                  |
| `username`        | X handle without the `@`                                 |
| `verified`        | Whether the account appears verified                     |
| `body`            | Tweet body text                                          |
| `time`            | Tweet timestamp in ISO format                            |
| `hashtags`        | Hashtags extracted from the tweet text and hashtag links |
| `has_media`       | True if the tweet contains media                         |
| `has_photo`       | True if the tweet contains a photo                       |
| `has_video`       | True if the tweet contains a video                       |
| `replies`         | Reply count                                              |
| `reposts`         | Repost count                                             |
| `likes`           | Like count                                               |
| `bookmarks`       | Bookmark count                                           |
| `views`           | View count                                               |
| `words_count`     | Count of words longer than 3 characters                  |
| `sentiment_score` | VADER compound sentiment score                           |
| `sentiment`       | Simple label derived from sentiment score                |

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
docker compose up --build
```

### 3. Verify the health endpoint

```bash
curl http://localhost:9096/health
```

Expected response:

```json
{"status":"ok"}
```

### 4. Verify the readiness endpoint

```bash
curl http://localhost:9096/ready
```

Expected response:

```json
{"status":"ready"}
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

Possible next steps if you keep expanding it:

- add caching for repeated timeline requests
- add a job queue for heavy timeline scrapes
- add structured logs
- add retries for transient browser failures
- expose additional X endpoints
- add rate limiting
- add metrics and health probes for orchestration

## Final note

This project is a scraper service, not a platform.

That is the point.

It stays focused, containerized, and easy to plug into whatever you build next.
