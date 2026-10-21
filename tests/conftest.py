from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import core.config
from core.cache import Cache
from core.http import HttpClient, set_client

FIXTURES = Path(__file__).parent / "fixtures"
KEYS = (
    "EXA_API_KEY",
    "TINYFISH_API_KEY",
    "GITHUB_TOKEN",
    "YOUTUBE_API_KEY",
    "PODCAST_INDEX_KEY",
    "PODCAST_INDEX_SECRET",
    "OPENALEX_EMAIL",
    "SEMANTIC_SCHOLAR_API_KEY",
)


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """No real .env and no real keys leak into tests."""
    monkeypatch.setattr(core.config, "_loaded", True)
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def http() -> Iterator[HttpClient]:
    client = HttpClient(Cache(":memory:"), backoff_base=0, rate_limits={}, sleep=lambda _: None)
    set_client(client)
    yield client
    set_client(None)
    client.close()


@pytest.fixture
def all_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in KEYS:
        monkeypatch.setenv(key, "test-value")
