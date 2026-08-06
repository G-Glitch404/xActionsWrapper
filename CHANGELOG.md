# Changelog

All notable changes to this project will be documented in this file.

The format loosely follows Keep a Changelog and the project adheres to Semantic Versioning.

## [Unreleased]

### Added

- Added WebSocket endpoints for streaming scraped tweets in real time.
- Added browser-side `stop_date` filtering to stop scrolling once older tweets are reached.
- Added shared scraping core used by both REST and WebSocket APIs.
- Added tweet enrichment pipeline.
- Added automatic sentiment analysis using VADER.
- Added `sentiment_score` and `sentiment` fields to every returned tweet.
- Added `words_count` metric to every returned tweet.
- Added normalized stop date handling across all scraping endpoints.
- Added richer request validation for all request models.
- Added detailed docstrings throughout the public API.

### Changed

- Refactored the API to remove duplicated scraping logic.
- Unified REST and WebSocket endpoints around a single scraping engine.
- Renamed timeline request field from `list_url` to `url`.
- Renamed timeline response field from `list_url` to `url`.
- Improved request model consistency across all endpoints.
- Improved response consistency between timeline and user scraping.
- Improved internal date normalization.
- Improved scraper architecture to support streaming output.
- Improved JavaScript runner structure and validation.
- Improved extraction pipeline for timeline scraping.
- Improved duplicate tweet filtering using tweet IDs.
- Improved timeout handling and scraper error reporting.
- Improved request validation and error messages.

### Enhanced Tweet Extraction

- Extract account display names.
- Extract usernames.
- Extract tweet IDs.
- Extract permanent tweet URLs.
- Detect verified accounts.
- Extract hashtags.
- Detect media attachments.
- Detect photos.
- Detect videos.
- Extract reply counts.
- Extract repost counts.
- Extract like counts.
- Extract bookmark counts.
- Extract view counts.
- Normalize engagement counters.
- Normalize extracted text.

### Performance

- Browser-side cutoff significantly reduces unnecessary scrolling.
- Streaming output reduces memory usage for large timeline scrapes.
- Shared scraping core reduces maintenance complexity.
- Removed duplicated endpoint implementations.
- Improved overall throughput for long-running timeline scrapes.

### Documentation

- Updated README to document the new API architecture.
- Documented WebSocket streaming endpoints.
- Documented `stop_date` support.
- Updated request and response examples.
- Improved endpoint documentation.
- Improved architecture documentation.
```