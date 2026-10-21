"""Regression tests for the independent review of phases 11-12 (one test per finding)."""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import respx

from core.content import parse_date
from core.dossier import dossier
from core.follow import FollowTarget, whats_new
from core.models import SourceName
from core.page import _link
from tests.conftest import load

SINCE = date(2026, 1, 15)


def _works(*items: dict[str, Any]) -> dict[str, Any]:
    return {"results": list(items)}


def test_malformed_dates_never_escape() -> None:
    assert parse_date("20260230T000000Z") is None
    assert parse_date(1e100) is None
    assert parse_date(True) is None
    target = FollowTarget(name="Ann Lee", podcasts=False)
    with respx.mock(assert_all_called=False) as router:
        router.get("https://api.gdeltproject.org/api/v2/doc/doc").mock(
            return_value=httpx.Response(
                200,
                json={
                    "articles": [
                        {
                            "url": "https://n.example/a",
                            "title": "Ann Lee story",
                            "seendate": "20260230T000000Z",
                        }
                    ]
                },
            )
        )
        r = whats_new([target], SINCE)
    assert [(i.url, i.date_kind) for i in r.newly_observed] == [("https://n.example/a", "unknown")]


def test_offsets_are_compared_in_utc() -> None:
    assert parse_date("2026-01-15T00:30:00+02:00") == date(2026, 1, 14)
    assert parse_date("2026-01-14T23:30:00-02:00") == date(2026, 1, 15)
    assert parse_date("2026-01-15T00:00:00Z") == date(2026, 1, 15)
    assert parse_date("2026-01-15") == date(2026, 1, 15)


def test_malformed_content_urls_do_not_abort_the_dossier() -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get("https://api.openalex.org/authors").mock(
            return_value=httpx.Response(200, json=load("openalex_authors.json"))
        )
        router.get("https://api.openalex.org/works").mock(
            return_value=httpx.Response(
                200,
                json=_works(
                    {
                        "id": "https://[invalid",
                        "display_name": "Broken one",
                        "publication_date": "2026-02-01",
                    },
                    {
                        "id": "http-not-a-url",
                        "display_name": "Broken two",
                        "publication_date": "2026-02-01",
                    },
                    {
                        "id": "https://openalex.org/W1",
                        "display_name": "Good work title here",
                        "publication_date": "2026-02-01",
                    },
                ),
            )
        )
        d = dossier("Geoffrey Hinton", sources=(SourceName.OPENALEX,))
    papers = [c.source_url for c in d.claims if c.field == "publication"]
    assert papers == ["https://openalex.org/W1"]


def test_same_name_targets_keep_separate_items_and_statuses() -> None:
    a = FollowTarget(name="Ann Lee", openalex="A1", podcasts=False, news=False)
    b = FollowTarget(name="Ann Lee", openalex="A2", podcasts=False, news=False)
    shared = {
        "id": "https://openalex.org/W9",
        "doi": "https://doi.org/10.1/shared",
        "display_name": "A coauthored paper title",
        "publication_date": "2026-03-01",
    }

    def by_author(request: httpx.Request) -> httpx.Response:
        if "A1" in request.url.params["filter"]:
            return httpx.Response(200, json=_works(shared))
        return httpx.Response(500)

    with respx.mock:
        respx.get("https://api.openalex.org/works").mock(side_effect=by_author)
        r = whats_new([a, b], SINCE)
    assert [i.target for i in r.published] == ["Ann Lee [openalex:A1]"]
    assert r.status["Ann Lee [openalex:A1] / openalex_works"] == "ok"
    assert r.status["Ann Lee [openalex:A2] / openalex_works"].startswith("error")

    with respx.mock:
        respx.get("https://api.openalex.org/works").mock(
            return_value=httpx.Response(200, json=_works(shared))
        )
        r2 = whats_new([a, b], SINCE)
    assert sorted(i.target for i in r2.published) == [
        "Ann Lee [openalex:A1]",
        "Ann Lee [openalex:A2]",
    ]


def test_link_destination_with_angle_brackets_stays_a_link() -> None:
    url = "https://doi.org/10.1002/(SICI)1097-0134(199704)27:4<514::AID-PROT6>3.0.CO;2-C"
    md = _link("Protein structure paper", url)
    dest = md[md.index("](<") + 3 : -2]
    assert "<" not in dest and ">" not in dest
    assert "%3C514::AID-PROT6%3E" in dest
    assert md.startswith("[Protein structure paper](<") and md.endswith(">)")


def test_semantic_scholar_reads_past_the_first_page() -> None:
    page1 = {
        "offset": 0,
        "next": 500,
        "data": [
            {
                "title": "Old paper from twenty twenty",
                "url": "https://www.semanticscholar.org/paper/old",
                "publicationDate": "2020-01-01",
                "year": 2020,
                "externalIds": {},
            }
        ],
    }
    page2 = {
        "offset": 500,
        "data": [
            {
                "title": "New paper from twenty twenty six",
                "url": "https://www.semanticscholar.org/paper/new",
                "publicationDate": "2026-05-01",
                "year": 2026,
                "externalIds": {},
            }
        ],
    }

    def paged(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=page1 if request.url.params["offset"] == "0" else page2)

    target = FollowTarget(name="Someone", semantic_scholar="7", podcasts=False, news=False)
    with respx.mock:
        route = respx.get("https://api.semanticscholar.org/graph/v1/author/7/papers").mock(
            side_effect=paged
        )
        r = whats_new([target], SINCE, limit=1)
    assert route.call_count == 2
    assert [i.url for i in r.published] == ["https://www.semanticscholar.org/paper/new"]


def test_same_title_different_dates_are_different_works() -> None:
    data = {
        "data": [
            {
                "title": "Recurring workshop paper title",
                "url": "https://www.semanticscholar.org/paper/a",
                "publicationDate": "2020-06-01",
                "year": 2020,
                "externalIds": {"DOI": "10.1/a"},
            },
            {
                "title": "Recurring workshop paper title",
                "url": "https://www.semanticscholar.org/paper/b",
                "publicationDate": "2026-06-01",
                "year": 2026,
                "externalIds": {"DOI": "10.1/b"},
            },
        ]
    }
    target = FollowTarget(name="Someone", semantic_scholar="8", podcasts=False, news=False)
    with respx.mock:
        respx.get("https://api.semanticscholar.org/graph/v1/author/8/papers").mock(
            return_value=httpx.Response(200, json=data)
        )
        r = whats_new([target], SINCE)
    assert [i.url for i in r.published] == ["https://doi.org/10.1/b"]


def test_release_in_an_old_repo_is_followed() -> None:
    repos = [
        {
            "full_name": "torvalds/oldtool",
            "html_url": "https://github.com/torvalds/oldtool",
            "fork": False,
            "created_at": "2019-01-01T00:00:00Z",
            "pushed_at": "2026-10-05T00:00:00Z",
        },
        {
            "full_name": "torvalds/stale",
            "html_url": "https://github.com/torvalds/stale",
            "fork": False,
            "created_at": "2018-01-01T00:00:00Z",
            "pushed_at": "2024-01-01T00:00:00Z",
        },
    ]
    releases = [
        {
            "html_url": "https://github.com/torvalds/oldtool/releases/tag/v2.0",
            "name": "v2.0",
            "tag_name": "v2.0",
            "published_at": "2026-10-05T12:00:00Z",
            "draft": False,
        },
        {
            "html_url": "https://github.com/torvalds/oldtool/releases/tag/v1.0",
            "name": "v1.0",
            "tag_name": "v1.0",
            "published_at": "2020-01-01T12:00:00Z",
            "draft": False,
        },
    ]
    target = FollowTarget(name="Linus Torvalds", github="torvalds", podcasts=False, news=False)
    with respx.mock:
        respx.get("https://api.github.com/users/torvalds/repos").mock(
            return_value=httpx.Response(200, json=repos)
        )
        stale = respx.get("https://api.github.com/repos/torvalds/stale/releases")
        respx.get("https://api.github.com/repos/torvalds/oldtool/releases").mock(
            return_value=httpx.Response(200, json=releases)
        )
        r = whats_new([target], SINCE)
    urls = [i.url for i in r.published]
    assert "https://github.com/torvalds/oldtool/releases/tag/v2.0" in urls
    assert "https://github.com/torvalds/oldtool/releases/tag/v1.0" not in urls
    assert "https://github.com/torvalds/oldtool" not in urls  # repo created 2019
    assert stale.call_count == 0  # no push since the cutoff, so its releases are not fetched
