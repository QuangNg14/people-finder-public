from __future__ import annotations

from typing import Any

import httpx
import respx

from core.models import SourceName, SourceQuery
from core.sources import SOURCES
from tests.conftest import load


def _user(request: httpx.Request) -> httpx.Response:
    login = request.url.path.rsplit("/", 1)[-1]
    profile: dict[str, Any] = load("github_user_torvalds.json")
    if login != "torvalds":
        profile = {
            **profile,
            "login": login,
            "name": None,
            "html_url": f"https://github.com/{login}",
        }
    return httpx.Response(200, json=profile)


@respx.mock
def test_search_by_handle_returns_enriched_profiles() -> None:
    respx.get("https://api.github.com/search/users").mock(
        return_value=httpx.Response(200, json=load("github_search_users.json"))
    )
    respx.get(url__regex=r"https://api\.github\.com/users/[^/]+$").mock(side_effect=_user)
    hits = SOURCES[SourceName.GITHUB].search(
        SourceQuery(person="torvalds", description=None, limit=5)
    )
    assert len(hits) == 5
    top = hits[0]
    assert top.url == "https://github.com/torvalds"
    assert top.kind == "profile" and top.source is SourceName.GITHUB
    assert top.payload["login"] == "torvalds" and top.payload["name"] == "Linus Torvalds"
    assert all(h.url.startswith("https://github.com/") for h in hits)


@respx.mock
def test_token_is_sent_when_present(monkeypatch: Any) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "tkn")
    route = respx.get("https://api.github.com/search/users").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    SOURCES[SourceName.GITHUB].search(SourceQuery(person="nobody", description=None))
    assert route.calls.last.request.headers["Authorization"] == "Bearer tkn"


@respx.mock
def test_discovery_turns_repo_owners_into_candidates() -> None:
    respx.get("https://api.github.com/search/users").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    respx.get("https://api.github.com/search/repositories").mock(
        return_value=httpx.Response(200, json=load("github_search_repos.json"))
    )
    respx.get(url__regex=r"https://api\.github\.com/users/[^/]+$").mock(side_effect=_user)
    hits = SOURCES[SourceName.GITHUB].search(
        SourceQuery(person=None, description="kernel development")
    )
    kinds = sorted(h.kind for h in hits)
    assert kinds == ["profile", "repo"]  # the Organization-owned repo is skipped
    assert {h.payload.get("login") or h.payload.get("owner_login") for h in hits} == {"torvalds"}


@respx.mock
def test_unknown_org_does_not_fail_the_source() -> None:
    respx.get("https://api.github.com/search/users").mock(
        return_value=httpx.Response(200, json=load("github_search_users.json"))
    )
    respx.get("https://api.github.com/orgs/nope/members").mock(return_value=httpx.Response(404))
    respx.get(url__regex=r"https://api\.github\.com/users/[^/]+$").mock(side_effect=_user)
    outcome = SOURCES[SourceName.GITHUB].run(
        SourceQuery(person="torvalds", description=None, org="nope", limit=2)
    )
    assert outcome.status == "ok" and outcome.hits
