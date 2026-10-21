"""Per-source isolation (D18): a deliberately failing source returns [] and never raises."""

from __future__ import annotations

import httpx
import pytest
import respx

from core.models import SourceName, SourceQuery
from core.sources import SOURCES


@pytest.mark.parametrize("name", list(SourceName))
@pytest.mark.parametrize("mode", ["http500", "garbage", "network"])
def test_failing_source_returns_empty(name: SourceName, mode: str, all_keys: None) -> None:
    with respx.mock(assert_all_called=False) as mock:
        if mode == "http500":
            mock.route().mock(return_value=httpx.Response(500))
        elif mode == "garbage":
            mock.route().mock(return_value=httpx.Response(200, text="<html>not json</html>"))
        else:
            mock.route().mock(side_effect=httpx.ConnectError("down"))
        source = SOURCES[name]
        q = SourceQuery(person="Ada Lovelace", description=None)
        assert source.search(q) == []
        assert source.run(q).status in {"error", "empty"}


def test_every_source_name_is_registered() -> None:
    assert set(SOURCES) == set(SourceName)
