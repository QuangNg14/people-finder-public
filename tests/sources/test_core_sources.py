from __future__ import annotations

import httpx
import pytest
import respx

from core.models import SourceName, SourceQuery
from core.sources import SOURCES
from core.sources.itunes import resolve_episode
from tests.conftest import load

Q = SourceQuery(person="Geoffrey Hinton", description=None, limit=10)


@respx.mock
def test_openalex(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENALEX_EMAIL", "me@example.com")
    route = respx.get("https://api.openalex.org/authors").mock(
        return_value=httpx.Response(200, json=load("openalex_authors.json"))
    )
    hits = SOURCES[SourceName.OPENALEX].search(Q)
    assert route.calls.last.request.url.params["mailto"] == "me@example.com"
    top = hits[0]
    assert top.url.startswith("https://openalex.org/A")
    assert top.payload["h_index"] == 145 and top.payload["orcid"].startswith("https://orcid.org/")
    assert top.payload["institutions"]


def test_openalex_skips_description_queries() -> None:
    assert SOURCES[SourceName.OPENALEX].search(SourceQuery(person=None, description="x")) == []


@respx.mock
def test_openalex_402_degrades() -> None:
    respx.get("https://api.openalex.org/authors").mock(return_value=httpx.Response(402))
    outcome = SOURCES[SourceName.OPENALEX].run(Q)
    assert outcome.status == "error" and outcome.hits == []


@respx.mock
def test_semantic_scholar() -> None:
    respx.get("https://api.semanticscholar.org/graph/v1/author/search").mock(
        return_value=httpx.Response(200, json=load("semantic_scholar_authors.json"))
    )
    hits = SOURCES[SourceName.SEMANTIC_SCHOLAR].search(Q)
    assert len(hits) == 3
    assert hits[0].url == "https://www.semanticscholar.org/author/2257301155"
    assert hits[0].payload["h_index"] == 11


@respx.mock
def test_semantic_scholar_sends_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "k")
    route = respx.get("https://api.semanticscholar.org/graph/v1/author/search").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    SOURCES[SourceName.SEMANTIC_SCHOLAR].search(Q)
    assert route.calls.last.request.headers["x-api-key"] == "k"


@respx.mock
def test_youtube(all_keys: None) -> None:
    respx.get("https://www.googleapis.com/youtube/v3/search").mock(
        return_value=httpx.Response(200, json=load("youtube_search.json"))
    )
    hits = SOURCES[SourceName.YOUTUBE].search(Q)
    assert [h.kind for h in hits] == ["profile", "video"]
    assert hits[0].url == "https://www.youtube.com/channel/UC123"
    assert hits[1].url == "https://www.youtube.com/watch?v=abc123"


def test_youtube_requires_key() -> None:
    assert SOURCES[SourceName.YOUTUBE].run(Q).status == "missing_key"


@respx.mock
def test_podcast_index_signs_requests(all_keys: None) -> None:
    route = respx.get("https://api.podcastindex.org/api/1.0/search/byperson").mock(
        return_value=httpx.Response(200, json=load("podcast_index_byperson.json"))
    )
    hits = SOURCES[SourceName.PODCAST_INDEX].search(Q)
    headers = route.calls.last.request.headers
    assert headers["X-Auth-Key"] == "test-value" and len(headers["Authorization"]) == 40
    assert [h.url for h in hits] == [
        "https://podcast.example.com/ep101",
        "https://podcastindex.org/podcast/56?episode=102",
    ]
    assert hits[0].payload["show"] == "AI Podcast"


@respx.mock
def test_itunes_episode_recipe() -> None:
    route = respx.get("https://itunes.apple.com/search").mock(
        return_value=httpx.Response(200, json=load("itunes_episodes.json"))
    )
    hits = SOURCES[SourceName.ITUNES].search(Q)
    assert route.calls.last.request.url.params["entity"] == "podcastEpisode"
    assert hits and all(h.kind == "episode" for h in hits)
    assert hits[0].url.startswith("https://podcasts.apple.com/")
    assert resolve_episode("anything") == hits[0].url


@respx.mock
def test_itunes_resolve_missing_episode_is_none() -> None:
    respx.get("https://itunes.apple.com/search").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    assert resolve_episode("nope") is None


@respx.mock
def test_gdelt_sorted_and_quoted() -> None:
    route = respx.get("https://api.gdeltproject.org/api/v2/doc/doc").mock(
        return_value=httpx.Response(200, json=load("gdelt_articles.json"))
    )
    hits = SOURCES[SourceName.GDELT].search(Q)
    assert route.calls.last.request.url.params["query"] == '"Geoffrey Hinton"'
    dates = [h.payload["published"] for h in hits]
    assert dates == sorted(dates, reverse=True)


@respx.mock
def test_gdelt_plain_text_error_degrades() -> None:
    respx.get("https://api.gdeltproject.org/api/v2/doc/doc").mock(
        return_value=httpx.Response(200, text="Your search contained a phrase that is too short")
    )
    assert SOURCES[SourceName.GDELT].run(Q).status == "error"


@respx.mock
def test_tinyfish(all_keys: None) -> None:
    route = respx.get("https://api.search.tinyfish.ai").mock(
        return_value=httpx.Response(200, json=load("tinyfish_news.json"))
    )
    hits = SOURCES[SourceName.TINYFISH_NEWS].search(Q)
    req = route.calls.last.request
    assert req.url.params["domain_type"] == "news" and req.headers["X-API-Key"] == "test-value"
    assert hits[0].payload["publisher"] == "Example News"
