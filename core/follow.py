"""Follow: "what's new since <date>" for a list of people (roadmap phase 11, D21).

Pull-based by design: nothing polls and nothing is stored but the HTTP cache. The watchlist is a
TOML file the caller owns. Two date semantics are kept apart:

- `published`: the provider states a publication date on or after `since`.
- `newly_observed`: only an observation time is known (GDELT `seendate`), or no usable date.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from core.content import ContentRequest, fetch_content, parse_date, valid_url
from core.models import Hit, SourceName, SourceQuery
from core.resolve import canonical_url, fold
from core.sources import SOURCES
from core.sources.base import BaseSource, SourceOutcome

TARGET_KEYS = {
    "name",
    "openalex",
    "semantic_scholar",
    "github",
    "youtube_channel",
    "podcasts",
    "news",
}
NAME_SOURCES: tuple[tuple[SourceName, str], ...] = (
    (SourceName.PODCAST_INDEX, "podcasts"),
    (SourceName.TINYFISH_NEWS, "news"),
    (SourceName.GDELT, "news"),
)
OBSERVED_ONLY = {SourceName.GDELT}


@dataclass(frozen=True, slots=True)
class FollowTarget:
    name: str
    openalex: str | None = None
    semantic_scholar: str | None = None
    github: str | None = None
    youtube_channel: str | None = None
    podcasts: bool = True
    news: bool = True

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("each followed person needs a name")

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> FollowTarget:
        unknown = set(raw) - TARGET_KEYS
        if unknown:
            raise ValueError(f"unknown watchlist keys: {', '.join(sorted(unknown))}")
        return cls(
            name=str(raw.get("name", "")),
            openalex=raw.get("openalex") or None,
            semantic_scholar=raw.get("semantic_scholar") or None,
            github=raw.get("github") or None,
            youtube_channel=raw.get("youtube_channel") or None,
            podcasts=bool(raw.get("podcasts", True)),
            news=bool(raw.get("news", True)),
        )

    def ids(self) -> ContentRequest:
        return ContentRequest(
            self.openalex, self.semantic_scholar, self.github, self.youtube_channel
        )

    def key(self) -> str:
        """Display name plus identifiers, e.g. "Ann Lee [openalex:A1]"."""
        ids = [
            f"{label}:{value}"
            for label, value in (
                ("openalex", self.openalex),
                ("semantic_scholar", self.semantic_scholar),
                ("github", self.github),
                ("youtube", self.youtube_channel),
            )
            if value
        ]
        return f"{self.name} [{', '.join(ids)}]" if ids else self.name


@dataclass(frozen=True, slots=True)
class FollowItem:
    person: str
    target: str  # FollowTarget.key(); unique per followed person, even with a shared name
    source: str
    kind: str
    title: str
    url: str
    date: str | None
    date_kind: str  # "published" | "observed" | "unknown"
    match: str  # "identifier" (cannot be a same-name stranger) | "name" (may be)


@dataclass(frozen=True, slots=True)
class FollowReport:
    since: str
    published: list[FollowItem]
    newly_observed: list[FollowItem]
    status: dict[str, str] = field(default_factory=dict)


def load_watchlist(path: Path | str) -> list[FollowTarget]:
    """Read `[[person]]` tables from a TOML file the caller owns."""
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    people = data.get("person")
    if not isinstance(people, list) or not people:
        raise ValueError("watchlist needs at least one [[person]] table")
    return [FollowTarget.from_dict(p) for p in people]


def _name_outcome(
    source: BaseSource, target: FollowTarget, since: date, limit: int
) -> SourceOutcome:
    start = datetime(since.year, since.month, since.day, tzinfo=UTC)
    q = SourceQuery(person=target.name, description=None, limit=limit, since=start)
    return source.run(q)


def _classify(
    hit: Hit, person: str, target: str, since: date, observed_only: bool
) -> tuple[str, FollowItem] | None:
    """Return ("published"|"newly_observed", item), or None when the item predates `since`."""
    match = str(hit.payload.get("match") or "name")
    d = parse_date(hit.payload.get("published"))

    def item(date_kind: str) -> FollowItem:
        return FollowItem(
            person=person,
            target=target,
            source=hit.source.value,
            kind=hit.kind,
            title=hit.title,
            url=hit.url,
            date=d.isoformat() if d else None,
            date_kind=date_kind,
            match=match,
        )

    if observed_only:
        if d is not None and d < since:
            return None
        return "newly_observed", item("observed" if d else "unknown")
    if d is None:
        year = hit.payload.get("year")
        if isinstance(year, int) and year < since.year:
            return None
        return "newly_observed", item("unknown")
    if d < since:
        return None
    return "published", item("published")


def _newest_first(items: list[FollowItem]) -> list[FollowItem]:
    # ISO dates sort lexically; undated items ("") land last under reverse order.
    return sorted(items, key=lambda i: i.date or "", reverse=True)


def _target_keys(people: list[FollowTarget]) -> list[str]:
    """Stable, unique key per target, so same-name people never share items or statuses."""
    keys: list[str] = []
    for p in people:
        base = p.key()
        key, n = base, 2
        while key in keys:
            key, n = f"{base} #{n}", n + 1
        keys.append(key)
    return keys


def whats_new(
    targets: Iterable[FollowTarget],
    since: date,
    *,
    limit: int = 10,
    registry: dict[SourceName, BaseSource] | None = None,
) -> FollowReport:
    reg = registry if registry is not None else SOURCES
    people = list(targets)
    if not people:
        return FollowReport(since=since.isoformat(), published=[], newly_observed=[])
    keys = _target_keys(people)
    published: list[FollowItem] = []
    observed: list[FollowItem] = []
    status: dict[str, str] = {}

    def per_target(t: FollowTarget) -> list[tuple[str, list[Hit], str, bool]]:
        batches: list[tuple[str, list[Hit], str, bool]] = []
        for o in fetch_content(t.ids(), since=since, limit=limit, registry=reg):
            batches.append((o.label, o.hits, o.status, False))
        for name, flag in NAME_SOURCES:
            source = reg.get(name)
            if source is None or not getattr(t, flag):
                continue
            outcome = _name_outcome(source, t, since, limit)
            label_status = outcome.status + (f" ({outcome.detail})" if outcome.detail else "")
            batches.append((name.value, outcome.hits, label_status, name in OBSERVED_ONLY))
        return batches

    with ThreadPoolExecutor(max_workers=min(len(people), 4)) as pool:
        results = list(pool.map(per_target, people))

    for target, key, batches in zip(people, keys, results, strict=True):
        for label, hits, st, observed_only in batches:
            status[f"{key} / {label}"] = st
            # Date eligibility first, then dedupe, so an old copy can never hide a new work.
            for h in hits:
                if not valid_url(h.url):
                    continue
                classified = _classify(h, target.name, key, since, observed_only)
                if classified is None:
                    continue
                bucket, item = classified
                (published if bucket == "published" else observed).append(item)

    return FollowReport(
        since=since.isoformat(),
        published=_dedupe_items(_newest_first(published)),
        newly_observed=_dedupe_items(_newest_first(observed)),
        status=status,
    )


def _dedupe_items(items: list[FollowItem]) -> list[FollowItem]:
    """Per target: same URL, or same kind + title + date (DOI/arXiv/OpenAlex copies), once."""
    seen: set[tuple[str, ...]] = set()
    out: list[FollowItem] = []
    for i in items:
        keys: set[tuple[str, ...]] = {(i.target, "u", canonical_url(i.url))}
        title = fold(i.title)
        if len(title) > 12:
            keys.add((i.target, "t", i.kind, title, i.date or "-"))
        if keys & seen:
            continue
        seen |= keys
        out.append(i)
    return out
