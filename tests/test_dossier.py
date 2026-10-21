from __future__ import annotations

import httpx
import respx

from core.dossier import build_dossier, claims_from_entity, dossier
from core.models import SourceName as S
from core.resolve import resolve_identity
from tests.conftest import load
from tests.helpers import hit


def _mock_all(router: respx.MockRouter) -> None:
    router.post("https://api.exa.ai/search").mock(
        return_value=httpx.Response(200, json=load("exa_people.json"))
    )
    router.get("https://api.openalex.org/authors").mock(
        return_value=httpx.Response(200, json=load("openalex_authors.json"))
    )
    router.get("https://api.semanticscholar.org/graph/v1/author/search").mock(
        return_value=httpx.Response(200, json=load("semantic_scholar_authors.json"))
    )
    router.get("https://api.github.com/search/users").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    router.get("https://www.googleapis.com/youtube/v3/search").mock(
        return_value=httpx.Response(200, json=load("youtube_search.json"))
    )
    router.get("https://api.podcastindex.org/api/1.0/search/byperson").mock(
        return_value=httpx.Response(200, json=load("podcast_index_byperson.json"))
    )
    router.get("https://itunes.apple.com/search").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    router.get("https://api.search.tinyfish.ai").mock(
        return_value=httpx.Response(200, json=load("tinyfish_news.json"))
    )
    router.get("https://api.gdeltproject.org/api/v2/doc/doc").mock(return_value=httpx.Response(429))


def test_dossier_for_known_person_cites_multiple_sources(all_keys: None) -> None:
    with respx.mock(assert_all_called=False) as router:
        _mock_all(router)
        d = dossier("Geoffrey Hinton", org="University of Toronto")
    sources = {c.source_name for c in d.claims}
    assert len(sources) >= 2, sources
    assert all(c.source_url.startswith("https://") for c in d.claims)
    fields = {c.field for c in d.claims}
    assert {"current_role", "h_index", "education", "news_mention"} <= fields
    assert S.GDELT in d.unavailable and "error" in d.source_status["gdelt"]
    assert S.EXA in d.contributing
    # The Leeds chef shares the name but no corroborating signal, so he is an alternate.
    assert any("Leeds" in str(h.payload.get("location")) for e in d.alternates for h in e.hits)
    assert not any("Leeds" in c.value for c in d.claims)


def test_dossier_without_exa_key_still_builds(all_keys: None, monkeypatch: object) -> None:
    import pytest

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    monkeypatch.delenv("EXA_API_KEY")
    with respx.mock(assert_all_called=False) as router:
        _mock_all(router)
        d = dossier("Geoffrey Hinton")
    assert S.EXA in d.unavailable
    assert d.source_status["exa"].startswith("missing_key")
    assert d.claims and all(c.source_url for c in d.claims)


def test_dossier_with_no_results_is_empty_not_guessed() -> None:
    with respx.mock(assert_all_called=False) as router:
        router.route().mock(return_value=httpx.Response(200, json={}))
        d = dossier("Nobody Atall")
    assert d.claims == []
    assert d.entity.display_name == "Nobody Atall"
    assert set(d.unavailable) == set(S)


def test_competing_values_are_both_kept_with_their_sources() -> None:
    a = hit(
        S.EXA,
        "https://x.example/ann",
        "Ann Lee",
        orgs=["Acme"],
        work_history=[
            {"title": "CTO", "dates": {"from": "2020", "to": None}, "company": {"name": "Acme"}},
            {
                "title": "Advisor",
                "dates": {"from": "2021", "to": None},
                "company": {"name": "Globex"},
            },
        ],
    )
    b = hit(S.GITHUB, "https://github.com/annlee", "Ann Lee", login="annlee", company="Acme")
    [entity] = resolve_identity([a, b])
    claims = claims_from_entity(entity)
    roles = {(c.value, c.source_url) for c in claims if c.field == "current_role"}
    assert roles == {("CTO at Acme", a.url), ("Advisor at Globex", a.url)}
    assert ("Acme", b.url) in {(c.value, c.source_url) for c in claims if c.field == "current_org"}


def test_uncitable_fields_are_dropped() -> None:
    h = hit(S.GITHUB, "https://github.com/x", "X", login="x", company=None, blog="")
    [entity] = resolve_identity([h])
    d = build_dossier(entity, [])
    fields = {c.field for c in d.claims}
    assert "current_org" not in fields and "website" not in fields
    assert d.entity.claim_count == len(d.claims)
