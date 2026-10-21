"""JSON-shaped entry points shared by the MCP server and the CLI."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime
from enum import Enum
from typing import Any

from core.discovery import discover as _discover
from core.dossier import dossier as _dossier
from core.follow import FollowReport, FollowTarget, load_watchlist, whats_new
from core.models import Dossier, Entity, Hit, SourceName
from core.page import render_markdown
from core.sources import describe_sources

HANDLE_FIELDS = {"handle_github", "handle_x", "handle_orcid", "website", "youtube_channel"}


def to_jsonable(obj: Any) -> Any:
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        return obj.isoformat()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple | set):
        return [to_jsonable(v) for v in obj]
    return obj


def _footer(unavailable: list[SourceName], status: dict[str, str]) -> str:
    if not unavailable:
        return "All sources contributed."
    parts = [f"{s}: {status.get(str(s), 'no results')}" for s in unavailable]
    return "Unavailable or empty: " + "; ".join(parts)


def _hit_summary(h: Hit) -> dict[str, Any]:
    return {"source": h.source.value, "kind": h.kind, "url": h.url, "title": h.title}


def _entity_summary(e: Entity) -> dict[str, Any]:
    return {
        "display_name": e.display_name,
        "handles": e.handles,
        "score": e.score,
        "evidence": [_hit_summary(h) for h in e.hits],
    }


def dossier_json(
    person: str, org: str | None = None, location: str | None = None, limit: int = 10
) -> dict[str, Any]:
    d: Dossier = _dossier(person, org=org, location=location, limit=limit)
    return {
        "person": d.entity.display_name,
        "handles": d.entity.handles,
        "score": d.entity.score,
        "claims": [to_jsonable(c) for c in d.claims],
        "contributing": [s.value for s in d.contributing],
        "unavailable": [s.value for s in d.unavailable],
        "source_status": d.source_status,
        "other_people_with_this_name": [_entity_summary(e) for e in d.alternates],
        "footer": _footer(d.unavailable, d.source_status),
        "generated_at": d.generated_at.isoformat(),
    }


def discover_json(
    description: str, location: str | None = None, org: str | None = None, limit: int = 20
) -> dict[str, Any]:
    r = _discover(description, location=location, org=org, limit=limit)
    return {
        "description": r.description,
        "candidates": [_entity_summary(e) for e in r.entities],
        "contributing": [s.value for s in r.contributing],
        "unavailable": [s.value for s in r.unavailable],
        "source_status": r.source_status,
        "footer": _footer(r.unavailable, r.source_status),
        "generated_at": r.generated_at,
    }


def find_handle_json(
    person: str, platform: str | None = None, org: str | None = None
) -> dict[str, Any]:
    d = _dossier(person, org=org, limit=5)
    handles = [
        {"field": c.field, "value": c.value, "source_url": c.source_url, "source": c.source_name}
        for c in d.claims
        if c.field in HANDLE_FIELDS and (platform is None or platform.lower() in c.field)
    ]
    return {
        "person": d.entity.display_name,
        "handles": to_jsonable(handles),
        "other_people_with_this_name": len(d.alternates),
        "footer": _footer(d.unavailable, d.source_status),
    }


def list_sources_json() -> list[dict[str, object]]:
    return describe_sources()


def footprint_page_text(
    person: str, org: str | None = None, location: str | None = None, limit: int = 10
) -> str:
    return render_markdown(_dossier(person, org=org, location=location, limit=limit))


def whats_new_json(people: list[dict[str, Any]], since: str, limit: int = 10) -> dict[str, Any]:
    report = whats_new(
        [FollowTarget.from_dict(p) for p in people], date.fromisoformat(since), limit=limit
    )
    return _follow_json(report)


def whats_new_from_file(path: str, since: str, limit: int = 10) -> dict[str, Any]:
    return _follow_json(whats_new(load_watchlist(path), date.fromisoformat(since), limit=limit))


def _follow_json(report: FollowReport) -> dict[str, Any]:
    return {
        "since": report.since,
        "published": to_jsonable(report.published),
        "newly_observed": to_jsonable(report.newly_observed),
        "status": report.status,
        "note": (
            "published: the provider states a publication date on or after `since`. "
            "newly_observed: only an observation date (GDELT) or no usable date is known. "
            "match=name items may belong to a same-name person."
        ),
    }
