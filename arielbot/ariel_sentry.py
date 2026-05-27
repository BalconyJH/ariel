from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
import httpx
import sentry_sdk


@contextmanager
def sentry_span(op: str, name: str, **data: Any) -> Iterator[Any]:
    with sentry_sdk.start_span(op=op, name=name) as span:
        for key, value in data.items():
            if value is not None:
                span.set_data(key, value)
        yield span


def sentry_http_request(method: str, url: str, **kwargs: Any) -> httpx.Response:
    return httpx.request(method.upper(), url, **kwargs)


def sentry_http_get(url: str, **kwargs: Any) -> httpx.Response:
    return sentry_http_request("GET", url, **kwargs)


def sentry_http_post(url: str, **kwargs: Any) -> httpx.Response:
    return sentry_http_request("POST", url, **kwargs)
