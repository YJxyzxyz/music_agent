"""外部 HTTP 请求的有限重试与 JSON 解析。"""
import logging
import time

import requests

from config import settings

logger = logging.getLogger(__name__)
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


def request_json(session, method: str, url: str, *, operation: str, **kwargs) -> dict:
    attempts = settings.api_retry_attempts
    kwargs.setdefault("timeout", settings.api_timeout)

    for attempt in range(1, attempts + 1):
        try:
            response = session.request(method, url, **kwargs)
            if response.status_code in RETRYABLE_STATUS and attempt < attempts:
                raise requests.HTTPError(
                    f"temporary HTTP {response.status_code}", response=response
                )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            retryable = not (
                isinstance(exc, requests.HTTPError)
                and exc.response is not None
                and exc.response.status_code not in RETRYABLE_STATUS
            )
            if attempt >= attempts or not retryable:
                logger.error("%s failed after %s attempt(s): %s", operation, attempt, exc)
                raise
            delay = settings.api_retry_backoff * (2 ** (attempt - 1))
            logger.warning(
                "%s failed (attempt %s/%s), retrying in %.1fs: %s",
                operation,
                attempt,
                attempts,
                delay,
                exc,
            )
            time.sleep(delay)

    raise RuntimeError(f"{operation} failed unexpectedly")
