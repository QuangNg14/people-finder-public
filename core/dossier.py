"""The depth planner: one person in, one per-field cited Dossier out (spec 4.2, 5.1).

Any field without a (value, source_url) pair is dropped, never guessed. Competing values (two
employers) are both kept with their own sources.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from typing import Any

from core.content import ContentRequest, dedupe_content, fetch_content
from core.engine import run_sources, split
from core.models import Claim, Dossier, Entity, Hit, SourceName, SourceQuery, utcnow
from core.resolve import fold, names_match, pipeline
from core.sources.base import BaseSource

DOSSIER_SOURCES: tuple[SourceName, ...] = (
    SourceName.EXA,
    SourceName.GITHUB,
    SourceName.OPENALEX,
    SourceName.SEMANTIC_SCHOLAR,
    SourceName.YOUTUBE,
    SourceName.PODCAST_INDEX,
    SourceName.ITUNES,
    SourceName.TINYFISH_NEWS,
    SourceName.GDELT,
)

CONTENT_FIELD = {
    "article": "news_mention",
    "episode": "podcast_appearance",
    "video": "video_appearance",
    "repo": "github_repo",
    "release": "github_release",
    "publication": "publication",
}


def _s(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _profile_fields(h: Hit) -> Iterator[tuple[str, str]]:
    p = h.payload
    yield "name", _s(p.get("name") or h.title)
    yield "location", _s(p.get("location"))
    if h.source is SourceName.EXA:
        for w in p.get("work_history") or []:
            title = _s(w.get("title"))
            company = _s((w.get("company") or {}).get("name"))
            role = " at ".join(x for x in (title, company) if x)
            current = not _s((w.get("dates") or {}).get("to"))
            yield ("current_role" if current else "past_role"), role
        for e in p.get("education_history") or []:
            inst = e.get("institution") or e.get("school") or {}
            school = _s(inst.get("name") if isinstance(inst, dict) else inst)
            yield "education", ", ".join(x for x in (_s(e.get("degree")), school) if x)
        research = p.get("research") or {}
        yield "h_index", _s(research.get("hIndex"))
        for area in (research.get("areas") or [])[:5]:
            yield "research_area", _s(area)
        for work in (research.get("notableWorks") or [])[:5]:
            yield "notable_work", _s(work.get("title"))
    elif h.source is SourceName.GITHUB:
        yield "handle_github", _s(p.get("login"))
        yield "current_org", _s(p.get("company"))
        yield "website", _s(p.get("blog"))
        yield "handle_x", _s(p.get("twitter_username"))
        yield "bio", _s(p.get("bio"))
        yield "public_repos", _s(p.get("public_repos"))
    elif h.source is SourceName.OPENALEX:
        yield "handle_orcid", _s(p.get("orcid"))
        yield "h_index", _s(p.get("h_index"))
        yield "works_count", _s(p.get("works_count"))
        yield "citation_count", _s(p.get("cited_by_count"))
        for inst in p.get("institutions") or []:
            yield "affiliation", _s(inst)
        for topic in p.get("topics") or []:
            yield "research_area", _s(topic)
    elif h.source is SourceName.SEMANTIC_SCHOLAR:
        yield "handle_orcid", _s(p.get("orcid"))
        yield "h_index", _s(p.get("h_index"))
        yield "paper_count", _s(p.get("paper_count"))
        yield "citation_count", _s(p.get("citation_count"))
        yield "website", _s(p.get("homepage"))
        for aff in p.get("affiliations") or []:
            yield "affiliation", _s(aff)
    elif h.source is SourceName.YOUTUBE:
        yield "youtube_channel", _s(h.title)


def _content_value(h: Hit) -> str:
    show = _s(
        h.payload.get("show")
        or h.payload.get("venue")
        or h.payload.get("publisher")
        or h.payload.get("domain")
    )
    date = _s(h.payload.get("published"))[:10]
    suffix = ", ".join(x for x in (show, date) if x)
    return f"{h.title} ({suffix})" if suffix and h.title else h.title


def claims_from_entity(entity: Entity) -> list[Claim]:
    claims: list[Claim] = []
    seen: set[tuple[str, str, str]] = set()
    base = max(0.3, min(1.0, entity.score))
    for h in entity.hits:
        if h.kind == "profile":
            pairs = list(_profile_fields(h))
            confidence = base
        else:
            pairs = [(CONTENT_FIELD.get(h.kind, h.kind), _content_value(h))]
            # Identifier-anchored content (works of this ORCID/OpenAlex author, repos of this login)
            # is as certain as the profile; content attached by name mention is weaker.
            identified = h.payload.get("match") == "identifier"
            confidence = base if identified else base * 0.6
        for field_name, value in pairs:
            key = (field_name, fold(value), h.url)
            # Drop-uncited rule: a field with no value or no URL never becomes a claim.
            if not value or not h.url or key in seen:
                continue
            seen.add(key)
            claims.append(
                Claim(
                    field=field_name,
                    value=value,
                    source_url=h.url,
                    source_name=h.source,
                    retrieved_at=h.retrieved_at,
                    confidence=round(confidence, 3),
                )
            )
    return claims


def build_dossier(
    entity: Entity,
    unavailable: list[SourceName] | None = None,
    *,
    contributing: list[SourceName] | None = None,
    source_status: dict[str, str] | None = None,
    alternates: list[Entity] | None = None,
) -> Dossier:
    claims = claims_from_entity(entity)
    return Dossier(
        entity=Entity(
            display_name=entity.display_name,
            handles=entity.handles,
            claim_count=len(claims),
            score=entity.score,
            hits=entity.hits,
        ),
        claims=claims,
        unavailable=list(unavailable or []),
        generated_at=utcnow(),
        contributing=list(contributing or sorted({c.source_name for c in claims})),
        source_status=dict(source_status or {}),
        alternates=list(alternates or []),
    )


def _pick(entities: list[Entity], q: SourceQuery) -> tuple[Entity | None, list[Entity]]:
    assert q.person is not None
    handle = q.person.lstrip("@").lower()
    for i, e in enumerate(entities):
        if e.handles.get("github", "").lower() == handle:
            return e, entities[:i] + entities[i + 1 :]
    matching = [e for e in entities if names_match(e.display_name, q.person)]
    if matching:
        top = matching[0]
        return top, [e for e in entities if e is not top]
    return None, entities


def _with_content(
    entity: Entity,
    limit: int,
    registry: dict[SourceName, BaseSource] | None,
    status: dict[str, str],
) -> Entity:
    """Add papers, repos and uploads fetched by the entity's own identifiers (phase 12)."""
    ids = ContentRequest(
        openalex=entity.handles.get("openalex"),
        semantic_scholar=entity.handles.get("semantic_scholar"),
        github=entity.handles.get("github"),
        youtube_channel=entity.handles.get("youtube"),
    )
    if ids.is_empty():
        return entity
    outcomes = fetch_content(ids, limit=limit, registry=registry)
    status.update({o.label: o.status for o in outcomes})
    known = {h.url for h in entity.hits}
    extra = [h for h in dedupe_content([h for o in outcomes for h in o.hits]) if h.url not in known]
    return replace(entity, hits=[*entity.hits, *extra], claim_count=entity.claim_count + len(extra))


def dossier(
    person: str,
    *,
    org: str | None = None,
    location: str | None = None,
    limit: int = 10,
    sources: tuple[SourceName, ...] = DOSSIER_SOURCES,
    registry: dict[SourceName, BaseSource] | None = None,
) -> Dossier:
    q = SourceQuery(person=person, description=None, org=org, location=location, limit=limit)
    outcomes = run_sources(sources, q, registry)
    contributing, unavailable, status = split(outcomes)
    entities = pipeline([h for o in outcomes for h in o.hits], q)
    top, others = _pick(entities, q)
    if top is None:
        top = Entity(display_name=person, handles={}, claim_count=0, score=0.0, hits=[])
    else:
        top = _with_content(top, limit, registry, status)
    # Same-name candidates are surfaced, never merged: a false merge is worse than a duplicate.
    alternates = [e for e in others if e.hits and names_match(e.display_name, top.display_name)]
    return build_dossier(
        top,
        unavailable,
        contributing=contributing,
        source_status=status,
        alternates=alternates[:5],
    )
