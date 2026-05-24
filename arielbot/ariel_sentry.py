from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from urllib.parse import urlsplit

import httpx
import sentry_sdk


def _span_url(url: str) -> str:
    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.netloc:
        return url
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


@contextmanager
def sentry_span(op: str, name: str, **data: Any) -> Iterator[Any]:
    with sentry_sdk.start_span(op=op, name=name) as span:
        for key, value in data.items():
            if value is not None:
                span.set_data(key, value)
        yield span


def sentry_http_request(method: str, url: str, **kwargs: Any) -> httpx.Response:
    method_name = method.upper()
    span_url = _span_url(url)
    with sentry_span(
        "http.client",
        f"{method_name} {span_url}",
        **{
            "http.method": method_name,
            "http.url": span_url,
        },
    ) as span:
        try:
            response = httpx.request(method_name, url, **kwargs)
        except Exception as exc:
            span.set_data("error.type", type(exc).__name__)
            raise
        span.set_http_status(response.status_code)
        span.set_data("http.status_code", response.status_code)
        return response


def sentry_http_get(url: str, **kwargs: Any) -> httpx.Response:
    return sentry_http_request("GET", url, **kwargs)


def sentry_http_post(url: str, **kwargs: Any) -> httpx.Response:
    return sentry_http_request("POST", url, **kwargs)
