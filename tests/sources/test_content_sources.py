from __future__ import annotations

from datetime import date

import httpx
import respx

from core.models import SourceName
from core.sources import SOURCES
from core.sources.github import GitHub
from core.sources.openalex import OpenAlex
from core.sources.semantic_scholar import SemanticScholar
from core.sources.youtube import YouTube
from tests.conftest import load


def _src[T](name: SourceName, cls: type[T]) -> T:
    s = SOURCES[name]
    assert isinstance(s, cls)
    return s


@respx.mock
def test_openalex_works_by_author_filters_and_links_doi() -> None:
    route = respx.get("https://api.openalex.org/works").mock(
        return_value=httpx.Response(200, json=load("openalex_works.json"))
    )
    hits = _src(SourceName.OPENALEX, OpenAlex).works_by_author(
        "https://openalex.org/A5108093963", since=date(2026, 7, 1), limit=3
    )
    params = route.calls.last.request.url.params
    assert params["filter"] == "author.id:A5108093963,from_publication_date:2026-07-01"
    assert params["sort"] == "publication_date:desc"
    assert [h.kind for h in hits] == ["publication"] * 3
    assert hits[0].url.startswith("https://doi.org/")
    assert hits[0].payload["published"] == "2026-09-28"


@respx.mock
def test_semantic_scholar_author_papers_prefers_doi() -> None:
    respx.get("https://api.semanticscholar.org/graph/v1/author/2257301155/papers").mock(
        return_value=httpx.Response(200, json=load("s2_author_papers.json"))
    )
    hits = _src(SourceName.SEMANTIC_SCHOLAR, SemanticScholar).author_papers("2257301155")
    urls = [h.url for h in hits]
    assert "https://doi.org/10.1007/s12559-026-10569-8" in urls
    dates = [h.payload.get("published") or "" for h in hits]
    assert dates == sorted(dates, reverse=True)
    assert any(h.payload["published"] == "2026-02-26" for h in hits)


@respx.mock
def test_github_user_repos_skips_forks() -> None:
    data = load("github_user_repos.json")
    data[0] = {**data[0], "fork": True}
    respx.get("https://api.github.com/users/torvalds/repos").mock(
        return_value=httpx.Response(200, json=data)
    )
    hits = _src(SourceName.GITHUB, GitHub).user_repos("@torvalds")
    assert [h.url for h in hits] == [
        "https://github.com/torvalds/HunspellColorize",
        "https://github.com/torvalds/AudioNoise",
    ]
    assert hits[0].payload["published"] == "2026-01-18T19:57:03Z"


@respx.mock
def test_youtube_channel_uploads_uses_uploads_playlist(all_keys: None) -> None:
    respx.get("https://www.googleapis.com/youtube/v3/channels").mock(
        return_value=httpx.Response(200, json=load("youtube_channels.json"))
    )
    items = respx.get("https://www.googleapis.com/youtube/v3/playlistItems").mock(
        return_value=httpx.Response(200, json=load("youtube_playlist_items.json"))
    )
    hits = _src(SourceName.YOUTUBE, YouTube).channel_uploads("UC123")
    assert items.calls.last.request.url.params["playlistId"] == "UU123"
    assert [h.url for h in hits] == [
        "https://www.youtube.com/watch?v=vid00000001",
        "https://www.youtube.com/watch?v=vid00000002",
    ]
    assert hits[0].payload["published"] == "2026-10-01T10:00:00Z"


@respx.mock
def test_youtube_channel_without_uploads_returns_empty(all_keys: None) -> None:
    respx.get("https://www.googleapis.com/youtube/v3/channels").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    assert _src(SourceName.YOUTUBE, YouTube).channel_uploads("UCnone") == []
