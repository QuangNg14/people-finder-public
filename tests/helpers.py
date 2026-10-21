from __future__ import annotations

from typing import Any

from core.models import Hit, SourceName, SourceQuery, utcnow


def hit(
    source: SourceName,
    url: str,
    name: str = "",
    kind: str = "profile",
    title: str | None = None,
    snippet: str = "",
    **payload: Any,
) -> Hit:
    if name:
        payload.setdefault("name", name)
    return Hit(
        source=source,
        kind=kind,
        url=url,
        title=title if title is not None else name,
        snippet=snippet,
        retrieved_at=utcnow(),
        payload=payload,
        provenance="test",
    )


def q(person: str | None = None, description: str | None = None, **kw: Any) -> SourceQuery:
    return SourceQuery(person=person, description=description, **kw)
