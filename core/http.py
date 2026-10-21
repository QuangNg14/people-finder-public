"""One httpx client for every source: retries, backoff, throttling, and the cache path.

No source implements its own retry or caching (roadmap phase 1).
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from core.cache import TTL_SEARCH, Cache
from core.config import cache_path

USER_AGENT = "people-finder/0.1 (+https://github.com/QuangNg14/people-finder)"
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
SECRET_PARAMS = frozenset({"key", "api_key", "apikey", "token"})

# (max requests, window seconds) per source. iTunes and GDELT are throttled by their operators.
RATE_LIMITS: dict[str, tuple[int, float]] = {
    "itunes": (15, 10.0),
    "gdelt": (1, 5.0),
    "semantic_scholar": (1, 1.0),
}


class SourceError(Exception):
    """A provider call failed after retries. Sources turn this into an empty result."""

    def __init__(self, source: str, message: str, status: int | None = None) -> None:
        super().__init__(f"{source}: {message}")
        self.source = source
        self.status = status


@dataclass(frozen=True, slots=True)
class HttpResult:
    status: int
    body: bytes
    from_cache: bool
    stale: bool

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


def cache_key(
    source: str, method: str, url: str, params: Mapping[str, Any] | None, body: Any
) -> str:
    public = sorted((k, v) for k, v in (params or {}).items() if k.lower() not in SECRET_PARAMS)
    material = json.dumps(
        [source, method.upper(), url, public, body],
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class _Throttle:
    def __init__(self, limits: Mapping[str, tuple[int, float]]) -> None:
        self._limits = dict(limits)
        self._calls: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def wait(self, source: str, sleep: Callable[[float], None]) -> None:
        limit = self._limits.get(source)
        if limit is None:
            return
        max_calls, window = limit
        while True:
            with self._lock:
                now = time.monotonic()
                calls = self._calls.setdefault(source, deque())
                while calls and now - calls[0] >= window:
                    calls.popleft()
                if len(calls) < max_calls:
                    calls.append(now)
                    return
                delay = window - (now - calls[0])
            sleep(delay)


class HttpClient:
    def __init__(
        self,
        cache: Cache | None = None,
        *,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        timeout: float = 20.0,
        rate_limits: Mapping[str, tuple[int, float]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.cache = cache if cache is not None else Cache(cache_path())
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._sleep = sleep
        self._throttle = _Throttle(RATE_LIMITS if rate_limits is None else rate_limits)
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"},
        )

    def get(
        self,
        source: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        ttl: int = TTL_SEARCH,
    ) -> HttpResult:
        return self.request(source, "GET", url, params=params, headers=headers, ttl=ttl)

    def post(
        self,
        source: str,
        url: str,
        *,
        json_body: Any,
        headers: Mapping[str, str] | None = None,
        ttl: int = TTL_SEARCH,
    ) -> HttpResult:
        return self.request(source, "POST", url, json_body=json_body, headers=headers, ttl=ttl)

    def request(
        self,
        source: str,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
        headers: Mapping[str, str] | None = None,
        ttl: int = TTL_SEARCH,
    ) -> HttpResult:
        # Headers are excluded from the key: they carry credentials and per-call timestamps.
        key = cache_key(source, method, url, params, json_body)
        cached = self.cache.get(key)
        if cached is not None:
            return HttpResult(cached.status, cached.body, from_cache=True, stale=False)

        last_status: int | None = None
        last_error = "no attempt made"
        for attempt in range(self.max_retries + 1):
            self._throttle.wait(source, self._sleep)
            try:
                resp = self._client.request(
                    method, url, params=params, json=json_body, headers=dict(headers or {})
                )
            except httpx.HTTPError as exc:
                last_status, last_error = None, type(exc).__name__
            else:
                if 200 <= resp.status_code < 300:
                    self.cache.put(key, source, resp.content, resp.status_code, ttl)
                    return HttpResult(resp.status_code, resp.content, from_cache=False, stale=False)
                last_status, last_error = resp.status_code, f"HTTP {resp.status_code}"
                if resp.status_code == 429:
                    stale = self.cache.get(key, allow_stale=True)
                    if stale is not None:
                        return HttpResult(stale.status, stale.body, from_cache=True, stale=True)
                if resp.status_code not in RETRY_STATUSES:
                    break
            if attempt < self.max_retries:
                self._sleep(self.backoff_base * (2**attempt))
        raise SourceError(source, last_error, last_status)

    def close(self) -> None:
        self._client.close()


_default: HttpClient | None = None
_default_lock = threading.Lock()


def get_client() -> HttpClient:
    global _default
    with _default_lock:
        if _default is None:
            _default = HttpClient()
        return _default


def set_client(client: HttpClient | None) -> None:
    """Swap the process-wide client. Tests use this to inject an in-memory cache."""
    global _default
    with _default_lock:
        _default = client
