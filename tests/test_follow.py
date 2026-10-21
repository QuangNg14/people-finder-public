from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from core.content import parse_date
from core.follow import FollowTarget, load_watchlist, whats_new
from tests.conftest import load

SINCE = date(2026, 1, 15)
HINTON = FollowTarget(
    name="Geoffrey Hinton",
    openalex="A5108093963",
    github="torvalds",
    youtube_channel="UC123",
)
GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"
TINYFISH = "https://api.search.tinyfish.ai"


def _mock_everything(router: respx.MockRouter) -> dict[str, respx.Route]:
    routes = {
        "openalex": router.get("https://api.openalex.org/works").mock(
            return_value=httpx.Response(200, json=load("openalex_works.json"))
        ),
        "github": router.get("https://api.github.com/users/torvalds/repos").mock(
            return_value=httpx.Response(200, json=load("github_user_repos.json"))
        ),
        "yt_channels": router.get("https://www.googleapis.com/youtube/v3/channels").mock(
            return_value=httpx.Response(200, json=load("youtube_channels.json"))
        ),
        "yt_items": router.get("https://www.googleapis.com/youtube/v3/playlistItems").mock(
            return_value=httpx.Response(200, json=load("youtube_playlist_items.json"))
        ),
        "podcast": router.get("https://api.podcastindex.org/api/1.0/search/byperson").mock(
            return_value=httpx.Response(200, json=load("podcast_index_byperson.json"))
        ),
        "gdelt": router.get(GDELT).mock(
            return_value=httpx.Response(
                200,
                json={
                    "articles": [
                        # Delayed indexing: GDELT saw it after `since`; its publication date is
                        # unknown to us, so it must never be reported as published.
                        {
                            "url": "https://news.example.org/a",
                            "title": "Profile of Geoffrey Hinton",
                            "seendate": "20261010T064500Z",
                            "domain": "news.example.org",
                        },
                        {
                            "url": "https://news.example.org/old",
                            "title": "Old item",
                            "seendate": "20250101T000000Z",
                            "domain": "news.example.org",
                        },
                    ]
                },
            )
        ),
        "tinyfish": router.get(TINYFISH).mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "url": "https://press.example.com/dated",
                            "title": "Dated story",
                            "date": "2026-10-10",
                            "publisher": "Press",
                        },
                        {"url": "https://press.example.com/undated", "title": "Undated story"},
                    ]
                },
            )
        ),
    }
    return routes


def test_published_and_newly_observed_are_kept_apart(all_keys: None) -> None:
    with respx.mock(assert_all_called=False) as router:
        routes = _mock_everything(router)
        r = whats_new([HINTON], SINCE)

    params = routes["openalex"].calls.last.request.url.params
    assert params["filter"].endswith("from_publication_date:2026-01-15")
    assert routes["gdelt"].calls.last.request.url.params["startdatetime"] == "20260115000000"

    assert r.published, r.status
    assert all(
        i.date_kind == "published" and i.date and i.date >= "2026-01-15" for i in r.published
    )
    pub_urls = {i.url for i in r.published}
    assert "https://www.youtube.com/watch?v=vid00000001" in pub_urls
    assert "https://www.youtube.com/watch?v=vid00000002" not in pub_urls  # 2025 upload
    assert "https://github.com/torvalds/HunspellColorize" in pub_urls
    assert "https://github.com/torvalds/AudioNoise" not in pub_urls  # created 2026-01-09
    assert "https://press.example.com/dated" in pub_urls
    # OpenAlex returns the arXiv DOI and the OpenAlex record of the same paper: shown once.
    oa_titles = [i.title for i in r.published if i.source == "openalex"]
    assert len(oa_titles) == len(set(oa_titles)) == 2

    observed = {i.url: i for i in r.newly_observed}
    assert observed["https://news.example.org/a"].date_kind == "observed"
    assert "https://news.example.org/old" not in observed
    assert observed["https://press.example.com/undated"].date_kind == "unknown"
    assert not any(i.source == "gdelt" for i in r.published)

    assert dates_sorted_desc([i.date or "" for i in r.published])
    by_source = {i.source: i.match for i in r.published}
    assert by_source["openalex"] == by_source["github"] == by_source["youtube"] == "identifier"
    assert by_source["tinyfish_news"] == "name"


def dates_sorted_desc(dates: list[str]) -> bool:
    return dates == sorted(dates, reverse=True)


def test_semantic_scholar_undated_paper_is_never_published() -> None:
    papers = {
        "data": [
            {
                "title": "Dated new paper title",
                "url": "https://www.semanticscholar.org/paper/1",
                "publicationDate": "2026-03-01",
                "year": 2026,
                "externalIds": {},
            },
            {
                "title": "Year only recent paper",
                "url": "https://www.semanticscholar.org/paper/2",
                "publicationDate": None,
                "year": 2026,
                "externalIds": {},
            },
            {
                "title": "Year only ancient paper",
                "url": "https://www.semanticscholar.org/paper/3",
                "publicationDate": None,
                "year": 2019,
                "externalIds": {},
            },
        ]
    }
    target = FollowTarget(
        name="Someone Researcher", semantic_scholar="42", podcasts=False, news=False
    )
    with respx.mock:
        respx.get("https://api.semanticscholar.org/graph/v1/author/42/papers").mock(
            return_value=httpx.Response(200, json=papers)
        )
        r = whats_new([target], SINCE)
    assert [i.url for i in r.published] == ["https://www.semanticscholar.org/paper/1"]
    assert [(i.url, i.date_kind) for i in r.newly_observed] == [
        ("https://www.semanticscholar.org/paper/2", "unknown")
    ]


def test_missing_key_and_failures_are_statuses_not_exceptions() -> None:
    target = FollowTarget(name="Ann Lee", openalex="A1", youtube_channel="UC1", news=False)
    with respx.mock(assert_all_called=False) as router:
        router.get("https://api.openalex.org/works").mock(return_value=httpx.Response(500))
        router.get("https://api.podcastindex.org/api/1.0/search/byperson")
        r = whats_new([target], SINCE)
    assert r.published == [] and r.newly_observed == []
    key = "Ann Lee [openalex:A1, youtube:UC1]"
    assert r.status[f"{key} / openalex_works"].startswith("error")
    assert r.status[f"{key} / youtube_uploads"].startswith("missing_key")
    assert r.status[f"{key} / podcast_index"].startswith("missing_key")


def test_second_run_is_served_from_cache(all_keys: None) -> None:
    with respx.mock(assert_all_called=False) as router:
        routes = _mock_everything(router)
        whats_new([HINTON], SINCE)
        calls = {k: r.call_count for k, r in routes.items()}
        whats_new([HINTON], SINCE)
        assert {k: r.call_count for k, r in routes.items()} == calls


def test_watchlist_toml(tmp_path: Path) -> None:
    f = tmp_path / "watch.toml"
    f.write_text(
        '[[person]]\nname = "Ann Lee"\ngithub = "annlee"\n\n'
        '[[person]]\nname = "Bo Tran"\nopenalex = "A9"\nnews = false\n',
        encoding="utf-8",
    )
    people = load_watchlist(f)
    assert [p.name for p in people] == ["Ann Lee", "Bo Tran"]
    assert people[0].github == "annlee" and people[1].news is False
    f.write_text('[[person]]\nname = "X"\nlinkedin = "x"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="unknown watchlist keys"):
        load_watchlist(f)
    f.write_text("title = 'empty'\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_watchlist(f)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-10-01", date(2026, 10, 1)),
        ("2026-10-01T10:00:00Z", date(2026, 10, 1)),
        ("20261010T064500Z", date(2026, 10, 10)),
        (1760000000, date(2025, 10, 9)),
        ("not a date", None),
        (None, None),
    ],
)
def test_parse_date(raw: object, expected: date | None) -> None:
    assert parse_date(raw) == expected
