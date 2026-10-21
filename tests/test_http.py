from __future__ import annotations

import httpx
import pytest
import respx

from core.cache import Cache
from core.http import HttpClient, SourceError, _Throttle, cache_key

URL = "https://api.example.com/search"


@respx.mock
def test_second_identical_request_is_served_from_cache(http: HttpClient) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(200, json={"n": 1}))
    first = http.get("demo", URL, params={"q": "x"})
    second = http.get("demo", URL, params={"q": "x"})
    assert route.call_count == 1
    assert not first.from_cache and second.from_cache
    assert second.json() == {"n": 1}


@respx.mock
def test_retries_transient_errors_then_succeeds(http: HttpClient) -> None:
    route = respx.get(URL).mock(
        side_effect=[httpx.Response(503), httpx.ConnectError("boom"), httpx.Response(200, json=[])]
    )
    assert http.get("demo", URL).json() == []
    assert route.call_count == 3


@respx.mock
def test_non_retryable_status_fails_fast(http: HttpClient) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(404))
    with pytest.raises(SourceError) as exc:
        http.get("demo", URL)
    assert exc.value.status == 404
    assert route.call_count == 1


@respx.mock
def test_429_serves_stale_cache() -> None:
    cache = Cache(":memory:")
    client = HttpClient(cache, backoff_base=0, rate_limits={}, sleep=lambda _: None)
    key = cache_key("demo", "GET", URL, None, None)
    cache.put(key, "demo", b'{"old": true}', 200, ttl_seconds=-1)  # already expired
    respx.get(URL).mock(return_value=httpx.Response(429))
    result = client.get("demo", URL)
    assert result.stale and result.json() == {"old": True}


@respx.mock
def test_exhausted_retries_raise(http: HttpClient) -> None:
    respx.get(URL).mock(return_value=httpx.Response(500))
    with pytest.raises(SourceError):
        http.get("demo", URL)


def test_cache_key_ignores_secret_params() -> None:
    a = cache_key("yt", "GET", URL, {"q": "x", "key": "secret-1"}, None)
    b = cache_key("yt", "GET", URL, {"q": "x", "key": "secret-2"}, None)
    assert a == b


def test_throttle_waits_when_window_full(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [100.0]
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr("core.http.time.monotonic", lambda: clock[0])
    throttle = _Throttle({"demo": (2, 10.0)})
    for _ in range(3):
        throttle.wait("demo", fake_sleep)
    assert sleeps == [10.0]
    throttle.wait("unthrottled", fake_sleep)
    assert sleeps == [10.0]
