from __future__ import annotations

from typing import Any

import httpx
import respx

from core.discovery import discover
from core.models import SourceName as S
from tests.conftest import load


def _user(request: httpx.Request) -> httpx.Response:
    profile: dict[str, Any] = load("github_user_torvalds.json")
    return httpx.Response(200, json=profile)


def test_discovery_returns_ranked_entities_with_evidence(all_keys: None) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.post("https://api.exa.ai/search").mock(
            return_value=httpx.Response(200, json=load("exa_people.json"))
        )
        router.get("https://api.github.com/search/users").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        router.get("https://api.github.com/search/repositories").mock(
            return_value=httpx.Response(200, json=load("github_search_repos.json"))
        )
        router.get(url__regex=r"https://api\.github\.com/users/[^/]+$").mock(side_effect=_user)
        router.get("https://api.search.tinyfish.ai").mock(return_value=httpx.Response(500))
        router.get("https://api.gdeltproject.org/api/v2/doc/doc").mock(
            return_value=httpx.Response(200, json={"articles": []})
        )
        r = discover("deep learning researchers and kernel developers", limit=10)
    assert r.entities, r.source_status
    assert all(e.hits for e in r.entities)
    names = {e.display_name for e in r.entities}
    assert "Linus Torvalds" in names and "Geoffrey Hinton" in names
    linus = next(e for e in r.entities if e.display_name == "Linus Torvalds")
    assert any(h.kind == "repo" for h in linus.hits)
    assert S.TINYFISH_NEWS in r.unavailable and S.GDELT in r.unavailable
    assert "exa news fallback used" in r.source_status["tinyfish_news"]
    assert set(r.contributing) == {S.EXA, S.GITHUB}


def test_discovery_with_no_keys_and_no_results() -> None:
    with respx.mock(assert_all_called=False) as router:
        router.route().mock(return_value=httpx.Response(200, json={"items": [], "articles": []}))
        r = discover("nobody in particular")
    assert r.entities == []
    assert S.EXA in r.unavailable and r.source_status["exa"].startswith("missing_key")
