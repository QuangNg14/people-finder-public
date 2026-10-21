from __future__ import annotations

import json

import httpx
import respx

from core.models import SourceName, SourceQuery
from core.sources import SOURCES
from core.sources.exa import Exa
from tests.conftest import load


@respx.mock
def test_missing_key_reports_unavailable_without_a_call() -> None:
    route = respx.post("https://api.exa.ai/search")
    outcome = SOURCES[SourceName.EXA].run(SourceQuery(person="Geoffrey Hinton", description=None))
    assert outcome.status == "missing_key" and "EXA_API_KEY" in outcome.detail
    assert outcome.hits == [] and route.call_count == 0


@respx.mock
def test_people_category_maps_structured_entity(all_keys: None) -> None:
    route = respx.post("https://api.exa.ai/search").mock(
        return_value=httpx.Response(200, json=load("exa_people.json"))
    )
    hits = SOURCES[SourceName.EXA].search(
        SourceQuery(person="Geoffrey Hinton", description=None, org="University of Toronto")
    )
    body = json.loads(route.calls.last.request.content)
    assert body["category"] == "people" and "University of Toronto" in body["query"]
    assert route.calls.last.request.headers["x-api-key"] == "test-value"
    assert len(hits) == 2
    p = hits[0].payload
    assert p["name"] == "Geoffrey Hinton" and p["location"].startswith("Toronto")
    assert p["work_history"] and p["current_roles"] == [
        "Professor Emeritus at University of Toronto"
    ]
    assert p["research"]["hIndex"] == 190
    assert "University of Toronto" in p["orgs"]


@respx.mock
def test_news_fallback(all_keys: None) -> None:
    route = respx.post("https://api.exa.ai/search").mock(
        return_value=httpx.Response(200, json=load("exa_news.json"))
    )
    source = SOURCES[SourceName.EXA]
    assert isinstance(source, Exa)
    hits = source.search_news(SourceQuery(person="Geoffrey Hinton", description=None))
    assert json.loads(route.calls.last.request.content)["category"] == "news"
    assert hits[0].kind == "article" and hits[0].url == "https://news.example.com/hinton-award"
