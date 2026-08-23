# Changelog

All notable changes to this project will be documented in this file.

The format loosely follows Keep a Changelog and the project adheres to Semantic Versioning.

## [Unreleased]

### Added

- Added WebSocket endpoints for streaming scraped tweets in real time.
- Added browser-side `stop_date` filtering to stop scrolling once older tweets are reached.
- Added a shared scraping core for REST and WebSocket APIs.
- Added a Python tweet enrichment and normalization pipeline.
- Added automatic sentiment analysis using VADER.
- Added `sentiment_score` and `sentiment` fields to returned tweets.
- Added `words_count`, `words_length`, and `tweet_length` metrics.
- Added `content_hash` for stable tweet content fingerprinting.
- Added `engagement_hash` for tracking engagement changes.
- Added `engagement_count` and `tweet_weight` derived metrics.
- Added normalized `replies_count`, `reposts`, `likes`, `bookmarks`, and `views`.
- Added `hashtags`, `cashtags`, and `found_urls` extraction.
- Added `has_media`, `has_photo`, and `has_video` fields.
- Added normalized account metadata including `account_name`, `username`, and `verified`.
- Added normalized tweet identity fields including `tweet_id` and `tweet_url`.
- Added strict X timeline URL validation for search, list, and profile URLs.
- Added support for X search URLs with a required `q` parameter.
- Added support for X List URLs.
- Added support for X profile URLs.
- Added rejection of unsupported domains and X paths before scraping starts.

### Changed

- Refactored the API to remove duplicated scraping logic.
- Unified REST and WebSocket endpoints around the shared scraping engine.
- Renamed timeline request field from `list_url` to `url`.
- Renamed timeline response field from `list_url` to `url`.
- Updated the public tweet response contract around the normalized `Tweet` model.
- Normalized raw xActions engagement values such as `74K`, `9.4K`, and `10M` into integers.
- Improved request model consistency across all endpoints.
- Improved date normalization and `stop_date` handling.
- Improved JavaScript runner structure and validation.
- Improved timeline extraction and duplicate filtering.
- Improved timeout handling and scraper error reporting.
- Improved incremental streaming behavior.
- Restricted timeline scraping to supported `https://x.com` URL patterns.
- Improved timeline request validation to reject unsupported X pages before invoking the scraper.

### Enhanced Tweet Extraction

- Extract account display names from the X author block.
- Extract usernames without the `@` prefix.
- Extract tweet IDs from tweet status URLs.
- Extract permanent tweet URLs.
- Detect verified accounts.
- Extract hashtags from tweet text and hashtag links.
- Extract cashtags from tweet text.
- Extract URLs from tweet text.
- Detect media attachments.
- Detect photos.
- Detect videos.
- Extract reply counts.
- Extract repost counts.
- Extract like counts.
- Extract bookmark counts.
- Extract view counts.
- Normalize tweet text before analysis and hashing.

### Tweet Model

- Introduced a richer normalized `Tweet` Pydantic model.
- Added `tweet_id`.
- Added `tweet_url`.
- Added `content_hash`.
- Added `engagement_hash`.
- Added `account_name`.
- Added `username`.
- Added `body`.
- Added `time`.
- Added `sentiment`.
- Added `verified`.
- Added `has_media`.
- Added `has_photo`.
- Added `has_video`.
- Added `engagement_count`.
- Added `tweet_weight`.
- Added `replies_count`.
- Added `reposts`.
- Added `likes`.
- Added `bookmarks`.
- Added `views`.
- Added `words_count`.
- Added `words_length`.
- Added `tweet_length`.
- Added `sentiment_score`.
- Added `hashtags`.
- Added `cashtags`.
- Added `found_urls`.

### Performance

- Browser-side `stop_date` filtering reduces unnecessary scrolling.
- Streaming output allows tweets to be consumed as they are discovered.
- Shared scraping logic reduces duplicated processing.
- Tweet IDs provide efficient duplicate detection during timeline scraping.
- Normalizing data once in Python reduces repeated parsing for downstream consumers.
- Improved long-running timeline processing by stopping when the requested cutoff is reached.

### Documentation

- Updated README to reflect the current API architecture.
- Documented the normalized `Tweet` response model.
- Documented newly extracted tweet metadata.
- Documented content and engagement hashes.
- Documented normalized engagement counters.
- Documented text metrics and sentiment enrichment.
- Updated REST response examples.
- Updated WebSocket response examples.
- Updated timeline response documentation.
- Updated output contract documentation.
- Improved architecture and request-flow documentation.
