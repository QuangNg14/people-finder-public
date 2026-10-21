"""The breadth planner: a description in, ranked candidate people out, each with evidence."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.engine import run_sources, split
from core.models import Entity, SourceName, SourceQuery, utcnow
from core.resolve import pipeline
from core.sources.base import BaseSource

DISCOVERY_SOURCES: tuple[SourceName, ...] = (
    SourceName.EXA,
    SourceName.GITHUB,
    SourceName.TINYFISH_NEWS,
    SourceName.GDELT,
)


@dataclass(frozen=True, slots=True)
class Discovery:
    description: str
    entities: list[Entity]
    unavailable: list[SourceName]
    contributing: list[SourceName]
    source_status: dict[str, str] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: utcnow().isoformat())


def discover(
    description: str,
    *,
    location: str | None = None,
    org: str | None = None,
    limit: int = 20,
    sources: tuple[SourceName, ...] = DISCOVERY_SOURCES,
    registry: dict[SourceName, BaseSource] | None = None,
) -> Discovery:
    q = SourceQuery(person=None, description=description, location=location, org=org, limit=limit)
    outcomes = run_sources(sources, q, registry)
    contributing, unavailable, status = split(outcomes)
    entities = [e for e in pipeline([h for o in outcomes for h in o.hits], q) if e.hits]
    # Evidence strength: entity score plus corroborating content, capped so volume can't dominate.
    ranked = sorted(
        entities,
        key=lambda e: e.score + 0.1 * min(sum(h.kind != "profile" for h in e.hits), 5),
        reverse=True,
    )
    return Discovery(
        description=description,
        entities=ranked[:limit],
        unavailable=unavailable,
        contributing=contributing,
        source_status=status,
    )
