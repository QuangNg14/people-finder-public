"""The types are the design (spec section 5). Everything else is plumbing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class SourceName(StrEnum):
    EXA = "exa"
    OPENALEX = "openalex"
    GITHUB = "github"
    YOUTUBE = "youtube"
    PODCAST_INDEX = "podcast_index"
    ITUNES = "itunes"
    GDELT = "gdelt"
    TINYFISH_NEWS = "tinyfish_news"
    SEMANTIC_SCHOLAR = "semantic_scholar"


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class SourceQuery:
    person: str | None  # None in discovery mode
    description: str | None  # None in dossier mode
    location: str | None = None
    org: str | None = None
    limit: int = 20
    since: datetime | None = None

    def __post_init__(self) -> None:
        if not (self.person or self.description):
            raise ValueError("SourceQuery needs a person or a description")
        if self.limit < 1:
            raise ValueError("limit must be >= 1")

    @property
    def text(self) -> str:
        """The primary query string: the person in dossier mode, else the description."""
        return (self.person or self.description or "").strip()


@dataclass(frozen=True, slots=True)
class Hit:
    """One raw-ish result from one source. Post-normalization, pre-resolution."""

    source: SourceName
    kind: str  # "profile" | "publication" | "video" | "episode" | "article" | "repo"
    url: str
    title: str
    snippet: str
    retrieved_at: datetime
    payload: dict[str, Any]
    provenance: str  # the exact query string that produced this


@dataclass(frozen=True, slots=True)
class Claim:
    """One asserted field about a person, bound to the page that asserts it.

    `source_url` has no default, so an uncited claim cannot be constructed (spec 5.1).
    """

    field: str
    value: str
    source_url: str
    source_name: SourceName
    retrieved_at: datetime
    confidence: float

    def __post_init__(self) -> None:
        if not isinstance(self.source_url, str) or not self.source_url.startswith(
            ("https://", "http://")
        ):
            raise ValueError(f"Claim {self.field!r} needs an http(s) source_url")
        if not self.value.strip():
            raise ValueError(f"Claim {self.field!r} has an empty value")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be within [0, 1]")


@dataclass(frozen=True, slots=True)
class Entity:
    """A resolved human. Not persisted. Exists for the duration of one query."""

    display_name: str
    handles: dict[str, str]
    claim_count: int
    score: float
    hits: list[Hit]


@dataclass(frozen=True, slots=True)
class Dossier:
    entity: Entity
    claims: list[Claim]
    unavailable: list[SourceName]  # named in the footer, never silently dropped
    generated_at: datetime
    contributing: list[SourceName] = field(default_factory=list)
    source_status: dict[str, str] = field(default_factory=dict)
    alternates: list[Entity] = field(default_factory=list)
