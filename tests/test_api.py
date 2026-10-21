from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import respx

from core.api import dossier_json, find_handle_json, list_sources_json, to_jsonable
from tests.conftest import load

ROOT = Path(__file__).resolve().parent.parent


def _server_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("people_core", ROOT / "mcp" / "people_core.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mcp_server_exposes_exactly_the_core_tools() -> None:
    server: Any = _server_module().server
    tools = asyncio.run(server.list_tools())
    assert sorted(t.name for t in tools) == [
        "discover",
        "dossier",
        "find_handle",
        "footprint_page",
        "list_sources",
        "whats_new",
    ]


def test_list_sources_reports_key_presence(monkeypatch: Any) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")
    by_name = {s["name"]: s for s in list_sources_json()}
    assert by_name["youtube"]["key_present"] is True and by_name["youtube"]["available"] is True
    assert by_name["exa"]["key_present"] is False and by_name["exa"]["available"] is False
    assert by_name["itunes"]["requires_key"] is False and by_name["itunes"]["key_present"] is None
    assert len(by_name) == 9


def _mock_github(router: respx.MockRouter) -> None:
    router.get("https://api.github.com/search/users").mock(
        return_value=httpx.Response(200, json=load("github_search_users.json"))
    )
    router.get(url__regex=r"https://api\.github\.com/users/[^/]+$").mock(
        return_value=httpx.Response(200, json=load("github_user_torvalds.json"))
    )
    router.route().mock(return_value=httpx.Response(200, json={}))


def test_dossier_json_is_serializable_and_has_footer() -> None:
    with respx.mock(assert_all_called=False) as router:
        _mock_github(router)
        out = dossier_json("torvalds")
    json.dumps(out)
    assert out["person"] == "Linus Torvalds"
    assert out["handles"]["github"] == "torvalds"
    assert "exa: missing_key" in out["footer"]
    assert all(c["source_url"].startswith("https://") for c in out["claims"])


def test_find_handle_filters_by_platform() -> None:
    with respx.mock(assert_all_called=False) as router:
        _mock_github(router)
        out = find_handle_json("torvalds", platform="github")
    assert [h["value"] for h in out["handles"]] == ["torvalds"]
    assert out["handles"][0]["source_url"] == "https://github.com/torvalds"


def test_to_jsonable_handles_enums_and_dates() -> None:
    from core.models import SourceName, utcnow

    assert to_jsonable({"s": SourceName.EXA, "t": utcnow()})["s"] == "exa"
