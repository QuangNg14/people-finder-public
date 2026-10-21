"""Content retrieval by identifier, shared by Follow and the dossier (roadmap phases 11-12).

Identifier-anchored content (works of OpenAlex author A, repos of GitHub login L) cannot belong to a
same-name stranger, so these hits are marked `match="identifier"`. Every call is isolated: one
failing source becomes a status, never an exception.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from functools import partial
from urllib.parse import urlsplit

from core.models import Hit, SourceName
from core.resolve import canonical_url, fold
from core.sources import SOURCES
from core.sources.base import BaseSource
from core.sources.github import GitHub
from core.sources.openalex import OpenAlex
from core.sources.semantic_scholar import SemanticScholar
from core.sources.youtube import YouTube

_GDELT_STAMP = re.compile(r"^(\d{4})(\d{2})(\d{2})T\d{6}Z$")
CONTENT_LABELS = frozenset(
    {
        "openalex_works",
        "semantic_scholar_papers",
        "github_repos",
        "github_releases",
        "youtube_uploads",
    }
)


@dataclass(frozen=True, slots=True)
class ContentRequest:
    """Identifiers for one person. Only identifiers, never names, select content here."""

    openalex: str | None = None
    semantic_scholar: str | None = None
    github: str | None = None
    youtube_channel: str | None = None

    def is_empty(self) -> bool:
        return not (self.openalex or self.semantic_scholar or self.github or self.youtube_channel)


@dataclass(frozen=True, slots=True)
class ContentOutcome:
    label: str
    hits: list[Hit]
    status: str


def parse_date(value: object) -> date | None:
    """Return the UTC calendar date, or None for anything unusable. Never raises.

    Accepts ISO dates and datetimes (offsets are converted to UTC before taking the date, to match
    Follow's midnight-UTC cutoff), GDELT `YYYYMMDDTHHMMSSZ`, and unix seconds.
    """
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        if isinstance(value, int | float):
            return datetime.fromtimestamp(value, UTC).date()
        text = str(value).strip()
        m = _GDELT_STAMP.match(text)
        if m:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if len(text) == 10:
            return date.fromisoformat(text)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(UTC)
        return parsed.date()
    except (ValueError, OverflowError, OSError):
        return None


def valid_url(url: object) -> bool:
    """http(s) with a host, and parseable. Malformed links are dropped, never cited."""
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return False
    try:
        parts = urlsplit(url)
        return bool(parts.hostname) and parts.scheme in ("http", "https")
    except ValueError:
        return False


def _mark(hits: list[Hit]) -> list[Hit]:
    return [replace(h, payload={**h.payload, "match": "identifier"}) for h in hits]


def _run(label: str, source: BaseSource, fn: Callable[[], list[Hit]]) -> ContentOutcome:
    missing = source.missing_keys()
    if missing:
        return ContentOutcome(label, [], "missing_key (set " + ", ".join(missing) + ")")
    try:
        hits = _mark([h for h in fn() if valid_url(h.url)])
    except Exception as exc:  # isolation: a content source never fails the caller
        return ContentOutcome(label, [], f"error ({type(exc).__name__})")
    status = "ok" if hits else "empty"
    if any(h.payload.get("list_truncated") for h in hits):
        status += " (list truncated by the provider page cap)"
    return ContentOutcome(label, hits, status)


def _title_key(h: Hit) -> str | None:
    """Fold proven copies only: same kind, same normalized title, same publication date."""
    title = fold(h.title)
    if len(title) <= 12:
        return None
    d = parse_date(h.payload.get("published"))
    return f"t:{h.kind}:{title}:{d.isoformat() if d else '-'}"


def dedupe_content(hits: list[Hit]) -> list[Hit]:
    """Drop repeats by canonical URL, and fold DOI/arXiv/OpenAlex copies of the same work.

    Two works that share a title but differ in date are kept apart (a 2020 and a 2026 paper with
    the same title are different works). Hits with unusable URLs are dropped.
    """
    seen: set[str] = set()
    out: list[Hit] = []
    for h in hits:
        if not valid_url(h.url):
            continue
        keys = {"u:" + canonical_url(h.url)}
        tkey = _title_key(h)
        if tkey:
            keys.add(tkey)
        if keys & seen:
            continue
        seen |= keys
        out.append(h)
    return out


def fetch_content(
    ids: ContentRequest,
    *,
    since: date | None = None,
    limit: int = 10,
    registry: dict[SourceName, BaseSource] | None = None,
) -> list[ContentOutcome]:
    reg = registry if registry is not None else SOURCES
    jobs: list[tuple[str, BaseSource, Callable[[], list[Hit]]]] = []
    oa = reg.get(SourceName.OPENALEX)
    if ids.openalex and isinstance(oa, OpenAlex):
        jobs.append(("openalex_works", oa, partial(oa.works_by_author, ids.openalex, since, limit)))
    s2 = reg.get(SourceName.SEMANTIC_SCHOLAR)
    # Semantic Scholar 429s quickly without a key, so it is only the fallback for papers.
    if ids.semantic_scholar and not ids.openalex and isinstance(s2, SemanticScholar):
        jobs.append(
            (
                "semantic_scholar_papers",
                s2,
                partial(s2.author_papers, ids.semantic_scholar, limit, since),
            )
        )
    gh = reg.get(SourceName.GITHUB)
    if ids.github and isinstance(gh, GitHub):
        jobs.append(("github_repos", gh, partial(gh.user_repos, ids.github, limit)))
        jobs.append(("github_releases", gh, partial(gh.user_releases, ids.github, since)))
    yt = reg.get(SourceName.YOUTUBE)
    if ids.youtube_channel and isinstance(yt, YouTube):
        jobs.append(
            ("youtube_uploads", yt, partial(yt.channel_uploads, ids.youtube_channel, limit))
        )
    if not jobs:
        return []
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        return list(pool.map(lambda job: _run(*job), jobs))
