WHITE RABBIT ARCHIVE RATE-LIMIT PATCH

Fixes initial Substack archive syncs that hit HTTP 429 Too Many Requests.

Changes:
- Enforces a safer minimum inter-request delay for live archive crawls.
- Honors Retry-After when Substack sends it.
- Adds exponential backoff with jitter for HTTP 429 and transient 5xx responses.
- Keeps request_delay_ms=0 behavior unchanged for tests.
- Preserves normal resumable sync behavior: already downloaded articles are skipped.

Install from the White Rabbit project root after extracting this ZIP:

    python .\white_rabbit_archive_rate_limit_patch\install_patch.py

Then continue the unfinished archive:

    python -m white_rabbit archive sync

Check progress:

    python -m white_rabbit archive status
