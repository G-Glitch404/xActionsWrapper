# xActions Wrapper

A FastAPI microservice for scraping X content through **xActions**, packaged to run inside Docker.

This project is built to keep scraping isolated, repeatable, and easy to plug into automation workflows without turning the host machine into a dependency mess. The service exposes a narrow HTTP API around browser-driven scraping, then returns structured JSON that can be consumed by other scripts, pipelines, or downstream analytics.

## What this project does

This app currently exposes two endpoints:

- scrape tweets from one account or multiple accounts, one by one
- scrape any X timeline URL, including list timelines and other timeline-style pages

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

- `src/items.py` contains Pydantic models
- `src/api.py` contains the FastAPI routes
- `src/main.py` contains the xActions execution helpers
- `src/xactions_runner.mjs` bridges Python to Node/xActions
- `src/__main__.py` starts the API server

That split keeps request validation, endpoint routing, and browser automation from getting tangled together.

## API endpoints

### `POST /v1/scrape/tweets`

Scrape tweets from one account or multiple accounts.

The request accepts a list of usernames and processes them one by one. This makes it easy to scrape a single account or batch several accounts in a single call.

#### Request body

```json
{
  "usernames": ["MustStopMurad", "elonmusk"],
  "limit": 10,
  "timeout_seconds": 120
}
```

#### Fields

| Field             | Type      | Description                                |
|-------------------|-----------|--------------------------------------------|
| `usernames`       | list[str] | X usernames to scrape                      |
| `limit`           | int       | Number of tweets to fetch for each account |
| `timeout_seconds` | int       | Maximum time allowed for each scrape       |

#### Response shape

```json
{
  "usernames": ["MustStopMurad", "elonmusk"],
  "limit": 10,
  "count": 2,
  "elapsed_ms": 18420,
  "results": [
    {
      "username": "MustStopMurad",
      "count": 10,
      "tweets": []
    },
    {
      "username": "elonmusk",
      "count": 10,
      "tweets": []
    }
  ]
}
```

### `POST /v1/scrape/list-timeline`

Scrape tweets from any timeline URL.

This endpoint is meant for timeline-style pages, including X list timelines and similar timeline views that can be reached from a URL.

#### Request body

```json
{
  "list_url": "https://x.com/i/lists/1234567890",
  "limit": 100,
  "timeout_seconds": 120
}
```

#### Fields

| Field             | Type | Description                                 |
|-------------------|------|---------------------------------------------|
| `list_url`        | str  | Full timeline URL                           |
| `limit`           | int  | Maximum number of timeline items to collect |
| `timeout_seconds` | int  | Maximum time allowed for the scrape         |

#### Response shape

```json
{
  "list_url": "https://x.com/i/lists/1234567890",
  "limit": 100,
  "count": 100,
  "elapsed_ms": 31204,
  "tweets": []
}
```

## What the timeline endpoint does

This endpoint treats the target as a live timeline page. That means the service loads the URL, scrolls through the visible content, and extracts tweet objects from the page.

It is not the same thing as scraping list members.

If the URL points to a list timeline, it returns the tweets shown in that timeline. If the URL points to another timeline-style page, the scraper treats it the same way as long as the page structure is compatible.

## Extracted tweet data

The scraper now returns richer tweet objects than the old version.

A typical extracted item can include:

```json
{
  "tweet_id": "1940123456789012345",
  "tweet_url": "https://x.com/user/status/1940123456789012345",
  "account_name": "Memecoin Daddy",
  "username": "Raghavak0nSol",
  "verified": true,
  "text": "3x $VOLE ...",
  "time": "2026-08-02T09:10:17.000Z",
  "hashtags": ["SOL", "VOLE"],
  "has_media": true,
  "has_photo": true,
  "has_video": false,
  "replies": 79,
  "reposts": 1119,
  "likes": 18594,
  "bookmarks": 1337,
  "views": 645918
}
```

### Fields returned by the scraper

| Field          | Meaning                                                  |
|----------------|----------------------------------------------------------|
| `tweet_id`     | Stable tweet identifier extracted from the status URL    |
| `tweet_url`    | Permanent link to the tweet                              |
| `account_name` | Clean display name from the author line                  |
| `username`     | X handle without the `@`                                 |
| `verified`     | Whether the account appears verified                     |
| `text`         | Tweet body text                                          |
| `time`         | Tweet timestamp in ISO format                            |
| `hashtags`     | Hashtags extracted from the tweet text and hashtag links |
| `has_media`    | True if the tweet contains media                         |
| `has_photo`    | True if the tweet contains a photo                       |
| `has_video`    | True if the tweet contains a video                       |
| `replies`      | Reply count                                              |
| `reposts`      | Repost count                                             |
| `likes`        | Like count                                               |
| `bookmarks`    | Bookmark count                                           |
| `views`        | View count                                               |

This is the data shape that makes the service useful for ranking, scoring, filtering, and downstream analysis.

## Request flow

The runtime flow is intentionally simple:

1. FastAPI receives the request
2. Pydantic validates the input
3. Python launches the Node runner
4. the runner starts xActions
5. Chromium loads the page
6. the scraper extracts data from the DOM
7. the runner returns JSON
8. Python returns the response to the client

This keeps the scraping logic hidden behind a clean HTTP boundary.

## Project layout

```text
xActionsWrapper/
├── src/
│   ├── __init__.py
│   ├── __main__.py
│   ├── api.py
│   ├── items.py
│   ├── main.py
│   └── xactions_runner.mjs
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── uv.lock
├── README.md
└── .env
```

## Requirements

You need:

- Docker
- Docker Compose
- an X auth cookie if the target page requires authentication

You do not need to install Python, Node.js, Chromium, or xActions on the host machine.

## Environment variables

The container uses these values:

| Variable                  | Purpose                                                           |
|---------------------------|-------------------------------------------------------------------|
| `XACTIONS_AUTH_TOKEN`     | X auth cookie passed into the container                           |
| `XACTIONS_SESSION_COOKIE` | Optional alias for the same value                                 |
| `MAX_CONCURRENT_SCRAPES`  | Limits how many scrape jobs can run at once                       |
| `DEFAULT_TIMEOUT_SECONDS` | Default timeout for scrape requests                               |
| `HOST`                    | host to connect to defualts to '0.0.0.0'                          |
| `PORT`                    | port to connect to over docker compose contianer defualts to 9096 |

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

## Curl tests

### Test 1: scrape tweets from accounts

```bash
curl -X POST http://localhost:9096/v1/scrape/tweets \
  -H "Content-Type: application/json" \
  -d '{
    "usernames": ["MustStopMurad", "elonmusk"],
    "limit": 10,
    "timeout_seconds": 120
  }'
```

### Test 2: scrape a timeline URL

```bash
curl -X POST http://localhost:9096/v1/scrape/list-timeline \
  -H "Content-Type: application/json" \
  -d '{
    "list_url": "https://x.com/i/lists/1234567890",
    "limit": 100,
    "timeout_seconds": 120
  }'
```

## What to expect when a scrape fails

A failed scrape does not always mean the code is broken.

Common causes include:

- the account is private
- the auth cookie is missing or invalid
- the target URL is wrong
- X changed the page structure
- the browser timed out
- the page was rate-limited
- the current session needs to be refreshed

Scraping failures are often page issues, not API issues.

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

## Design goals

The project is built to stay small and readable.

The goal is not to hide the logic behind abstractions that make debugging harder.

The goal is to keep each layer obvious:

- validation
- execution
- browser automation
- JSON response

That makes the service easier to extend later without turning it into a mess.

## Future ideas

Possible next steps if you keep expanding it:

- add caching for repeated timeline requests
- add a job queue for heavy timeline scrapes
- store output in SQLite or Postgres
- add structured logs
- add retries for transient browser failures
- expose additional X endpoints
- add rate limiting

## Final note

This project is a scraper service, not a platform.

That is the point.

It stays focused, containerized, and easy to plug into whatever you build next.
