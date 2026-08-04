# xActions Wrapper

A small FastAPI microservice for scraping X data through **xActions**, packaged to run inside Docker.

The goal is simple: expose a clean HTTP API around a browser-based scraper, keep the runtime isolated, and make the service predictable enough to drop into a larger automation pipeline.

## What this project is for

This app wraps xActions behind two HTTP endpoints:

- scrape tweets from one account or multiple accounts, one by one
- scrape tweets from an X list timeline

It is intentionally narrow in scope. The service does not try to be a general data platform, a queue worker, or a database-backed scraper farm. It is a small microservice with a focused job: receive a request, validate it, run the scrape, return JSON.

That design keeps the code easier to reason about and much easier to deploy.

## Why this exists

Running browser automation directly on a host machine becomes messy fast.

xActions needs the right mix of:

- Python
- Node.js
- Chromium and its system libraries
- a working cookie/session if the page requires authentication

When those dependencies live on the host, they drift. One update breaks another project. One missing library breaks Chromium. One package manager pollutes the next environment.

Docker solves that by packaging the whole stack into one image. The container carries the exact runtime it needs, and nothing else.

## Why Docker is the right fit here

This project is a good candidate for a container for a few practical reasons.

### 1. Reproducibility

The same image should work the same way on a laptop, a VPS, or a build server.

### 2. Isolation

The container keeps Python, Node.js, xActions, and Chromium away from your host system.

### 3. Easier deployment

Instead of setting up a local Python environment, a Node environment, and Chromium dependencies separately, you build one image and run one container.

### 4. Better failure boundaries

If the scraper fails, it fails inside the container. Your host remains clean.

### 5. Easier upgrades

You can rebuild the image when you want to change xActions, Chromium, or the Python runtime without rewriting the rest of your system.

## About the Python 3.12 / environment issue

A common source of confusion in projects like this is not Python itself, but the environment around it.

You may see issues like:

- packages installed into one environment but the app starts with another
- `uv` syncing dependencies into a different interpreter than the one used at runtime
- `uvicorn` or another dependency missing even though installation appeared successful
- local Python behaving differently from the container Python

That is why this project is container-first.

The image controls the Python version, the installed dependencies, and the startup command. That removes a lot of the uncertainty that comes with local system Python setups.

If you ever see a `ModuleNotFoundError` for `uvicorn` or another package, the first thing to check is whether the app is running inside the same environment where dependencies were installed.

## Architecture

The project is split into a few small pieces:

- `src/items.py` contains Pydantic models
- `src/api.py` contains the FastAPI routes
- `src/main.py` contains the xActions execution helpers
- `src/xactions_runner.mjs` bridges Python to Node/xActions
- `src/__main__.py` starts the API server

This keeps the API code separate from the scraper execution code. That matters when the project grows, because route definitions, request validation, and browser logic tend to evolve at different speeds.

## API endpoints

### `POST /v1/scrape/tweets`

Scrape tweets from one account or multiple accounts.

The request accepts a list of usernames and processes them one by one.

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

#### Response example

```json
{
  "usernames": [
    "MustStopMurad",
    "elonmusk"
  ],
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

Scrape tweets from the timeline of an X list.

This endpoint is for the list page itself, not the list members endpoint.

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
| `list_url`        | str  | Full X list URL                             |
| `limit`           | int  | Maximum number of timeline items to collect |
| `timeout_seconds` | int  | Maximum time allowed for the scrape         |

#### Response example

```json
{
  "list_url": "https://x.com/i/lists/1234567890",
  "limit": 100,
  "count": 100,
  "elapsed_ms": 31204,
  "tweets": []
}
```

## What the list endpoint is doing

There is an important distinction here.

A list on X can mean two different things:

- the list members
- the timeline of posts shown when you open the list page

This service is built for the second case: the timeline view.

That means the endpoint treats the list page like a live feed and extracts the tweets visible there. It is not the same as asking for every member of the list.

## How the service works

The request flow is deliberately simple:

1. a client sends HTTP to FastAPI
2. Pydantic validates the payload
3. Python launches the Node runner
4. the runner starts xActions with Chromium
5. xActions opens the page and scrapes the content
6. JSON is returned to Python
7. Python returns a structured HTTP response

This keeps the scraper behind a clean interface. Other services do not need to know how xActions works internally.

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
- an X auth cookie if the page or account requires authentication

You do not need to install Python, Node.js, Chromium, or xActions on the host machine.

## Environment variables

The container uses these variables:

| Variable                  | Purpose                                                 |
|---------------------------|---------------------------------------------------------|
| `XACTIONS_AUTH_TOKEN`     | X auth cookie passed into the container                 |
| `XACTIONS_SESSION_COOKIE` | optional alias for the same value                       |
| `MAX_CONCURRENT_SCRAPES`  | limits how many scrape jobs can run at once             |
| `DEFAULT_TIMEOUT_SECONDS` | default timeout for scrape requests                     |
| `PORT`                    | optional port override if you want to customize Compose |

## Docker setup

### 1. Create your `.env`

Place this next to `docker-compose.yml`:

```env
XACTIONS_AUTH_TOKEN=your_x_auth_cookie_here
PORT=9096
```

Do not hardcode the cookie into the image.

### 2. Build and start the service

```bash
docker compose up --build
```

### 3. Check the health endpoint

```bash
curl http://localhost:9096/health
```

Expected response:

```json
{"status":"ok"}
```

## Running locally with `uv`

The container is the preferred way to run this service, but local development is still possible if your environment is already set up.

Typical local flow:

```bash
uv sync
uv run python -m src
```

If the local runtime starts acting strangely, move back to Docker. That is the more reliable path for this project.

## Why the service is a microservice

This project is small by design.

It is not trying to manage storage, analytics, scheduling, queues, dashboards, or long-term state.

It just exposes a small API that other tools can call.

That makes it a good microservice candidate:

- it has a narrow responsibility
- it is easy to deploy independently
- it can be called from Python, Node, cron jobs, or another backend
- it can be replaced or upgraded without touching the rest of the system

That is useful when you want to integrate scraping into a larger workflow without turning the scraper itself into a monolith.

## Curl tests

### Test 1: scrape tweets from accounts

```bash
curl -X POST http://localhost:9096/v1/scrape/tweets   -H "Content-Type: application/json"   -d '{
    "usernames": ["MustStopMurad", "elonmusk"],
    "limit": 10,
    "timeout_seconds": 120
  }'
```

### Test 2: scrape a list timeline

```bash
curl -X POST http://localhost:9096/v1/scrape/list-timeline   -H "Content-Type: application/json"   -d '{
    "list_url": "https://x.com/i/lists/1234567890",
    "limit": 100,
    "timeout_seconds": 120
  }'
```

## What to expect when a scrape fails

A failed scrape does not always mean the code is broken.

Possible causes include:

- the account is private
- the cookie is missing or invalid
- X changed the page structure
- the browser timed out
- the list URL is wrong
- the account or list is rate-limited

In other words, scraping problems often come from the page, not just the code.

## Troubleshooting

### `ModuleNotFoundError: uvicorn`

This means Python is starting outside the environment where `uvicorn` was installed.

Common fixes:

- check that `uvicorn` is in `pyproject.toml`
- make sure the container is built after dependency changes
- make sure `uv sync` and the runtime interpreter match

### `xactions: command not found`

This usually means xActions is not installed in the path your shell is using.

Inside Docker, this should not be a problem if the image installs xActions correctly during build.

### Empty tweet output

If the endpoint returns an empty array, common reasons are:

- the page did not expose tweet cards
- the account is private or inaccessible
- the auth cookie is missing
- the target list URL is incorrect
- the browser session needs to be refreshed

### Chromium launch errors

If Chromium refuses to start, check the image and container flags first.

Typical causes:

- missing shared libraries
- sandbox restrictions
- incorrect executable path
- incomplete browser installation

## Design goals

The project is intentionally kept small and readable.

The goal is not to hide everything behind magic.

The goal is to make each layer obvious:

- request validation
- execution
- browser automation
- JSON response

That makes the service easier to debug and easier to extend later.

## Future ideas

Possible next steps if you expand the service:

- add caching for repeated requests
- add rate limiting
- add queue-based bulk scraping
- store results in SQLite or Postgres
- add a retry strategy for transient page failures
- expose a profile endpoint
- add structured logs

## Final note

This project is a small scraper service, not a platform.

That is the point.

It is meant to stay clean, containerized, and easy to plug into whatever you build next.
