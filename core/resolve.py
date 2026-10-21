"""Normalize, dedupe, rank, and resolve hits into entities (spec section 8).

Matching signals, strongest first: ORCID, GitHub login, shared personal domain, name plus a
corroborating org, name plus location, name alone. A merge needs a weighted score of at least
MERGE_THRESHOLD and hits from two independent sources (D15): name alone never merges.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from core.models import Entity, Hit, SourceName, SourceQuery

WEIGHTS = {
    "orcid": 1.0,
    "github": 0.9,
    "domain": 0.7,
    "name_org": 0.5,
    "name_location": 0.25,
    "name": 0.2,
}
MERGE_THRESHOLD = 0.7

SOURCE_WEIGHT: dict[SourceName, float] = {
    SourceName.EXA: 1.0,
    SourceName.GITHUB: 0.8,
    SourceName.OPENALEX: 0.8,
    SourceName.SEMANTIC_SCHOLAR: 0.7,
    SourceName.YOUTUBE: 0.6,
    SourceName.PODCAST_INDEX: 0.5,
    SourceName.ITUNES: 0.5,
    SourceName.TINYFISH_NEWS: 0.5,
    SourceName.GDELT: 0.4,
}

# Hosts that are platforms, not personal domains, so sharing one proves nothing.
SHARED_HOSTS = frozenset(
    {
        "github.com",
        "github.io",
        "linkedin.com",
        "twitter.com",
        "x.com",
        "medium.com",
        "substack.com",
        "youtube.com",
        "google.com",
        "sites.google.com",
        "orcid.org",
        "facebook.com",
        "instagram.com",
        "scholar.google.com",
        "researchgate.net",
        "academia.edu",
        "wordpress.com",
        "blogspot.com",
        "notion.site",
        "linktr.ee",
    }
)
ORG_STOPWORDS = frozenset({"inc", "llc", "ltd", "corp", "corporation", "co", "the", "company"})
_GITHUB_PROFILE = re.compile(r"^https?://(?:www\.)?github\.com/([A-Za-z0-9-]{1,39})/?$")
_ORCID = re.compile(r"(\d{4}-\d{4}-\d{4}-\d{3}[\dX])")


# --- text helpers -----------------------------------------------------------------------------


def fold(text: str) -> str:
    """Casefold, strip accents, and reduce to alphanumeric tokens separated by single spaces."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^0-9a-z]+", " ", ascii_only.casefold()).split())


def names_match(a: str | None, b: str | None) -> bool:
    ta, tb = fold(a or "").split(), fold(b or "").split()
    if not ta or not tb:
        return False
    if ta == tb:
        return True
    if len(ta) < 2 or len(tb) < 2 or ta[-1] != tb[-1]:
        return False
    fa, fb = ta[0], tb[0]
    # "Geoffrey Hinton" ~ "Geoffrey E. Hinton" ~ "G. Hinton". Weak by design (weight 0.2).
    return fa == fb or (len(fa) == 1 and fb.startswith(fa)) or (len(fb) == 1 and fa.startswith(fb))


def name_in_text(name: str, text: str) -> bool:
    tokens = fold(name).split()
    if len(tokens) < 2:
        return False
    hay = f" {fold(text)} "
    return f" {' '.join(tokens)} " in hay or f" {tokens[0]} {tokens[-1]} " in hay


def org_tokens(org: str | None) -> frozenset[str]:
    return frozenset(t for t in fold(org or "").split() if t not in ORG_STOPWORDS and len(t) > 1)


def orgs_overlap(a: Iterable[str], b: Iterable[str]) -> bool:
    ta = [org_tokens(x) for x in a]
    tb = [org_tokens(x) for x in b]
    return any(x and y and (x <= y or y <= x) for x in ta for y in tb)


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    query = urlencode(
        [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_")]
    )
    path = parts.path.rstrip("/") or ""
    return urlunsplit((parts.scheme.lower() or "https", host, path, query, ""))


def _dedupe_key(url: str) -> str:
    return canonical_url(url).replace("http://", "https://", 1)


def personal_domain(url: str | None) -> str | None:
    if not url:
        return None
    if "://" not in url:
        url = "https://" + url
    host = urlsplit(url).netloc.lower().removeprefix("www.")
    if not host or "." not in host:
        return None
    if host in SHARED_HOSTS or any(host.endswith("." + h) for h in SHARED_HOSTS):
        return None
    return host


# --- pipeline stages --------------------------------------------------------------------------


def normalize(hits: list[Hit]) -> list[Hit]:
    return [
        replace(h, url=canonical_url(h.url), title=" ".join(h.title.split()))
        for h in hits
        if h.url.startswith(("http://", "https://"))
    ]


def dedupe(hits: list[Hit]) -> list[Hit]:
    """Cross-source dedupe on canonical URL; syndicated copies collapse on (kind, title)."""
    seen: set[str] = set()
    out: list[Hit] = []
    for h in hits:
        keys = {"u:" + _dedupe_key(h.url)}
        if h.kind in ("article", "episode") and len(fold(h.title)) > 20:
            keys.add(f"t:{h.kind}:{fold(h.title)}")
        if keys & seen:
            continue
        seen |= keys
        out.append(h)
    return out


def _hit_text(h: Hit) -> str:
    extras = [str(v) for k, v in h.payload.items() if isinstance(v, str | list) and k != "name"]
    return " ".join([h.title, h.snippet, *extras])


def relevance(h: Hit, q: SourceQuery) -> float:
    score = SOURCE_WEIGHT.get(h.source, 0.5) * 0.3
    text = _hit_text(h)
    if q.person:
        name = h.payload.get("name") or h.title
        if names_match(str(name), q.person):
            score += 1.0
        elif name_in_text(q.person, text):
            score += 0.6
        elif fold(q.person.lstrip("@")) == fold(str(h.payload.get("login", ""))):
            score += 1.0
    if q.description:
        terms = {t for t in fold(q.description).split() if len(t) > 3}
        if terms:
            hay = set(fold(text).split())
            score += len(terms & hay) / len(terms)
    if q.org and orgs_overlap([q.org], _orgs(h)):
        score += 0.3
    if q.location and fold(q.location) in fold(str(h.payload.get("location", ""))):
        score += 0.2
    return round(score, 4)


def rank(hits: list[Hit], q: SourceQuery) -> list[Hit]:
    return sorted(hits, key=lambda h: relevance(h, q), reverse=True)


# --- identity signals and clustering ----------------------------------------------------------


def _orgs(h: Hit) -> list[str]:
    orgs = h.payload.get("orgs") or []
    company = h.payload.get("company")
    return [str(o) for o in [*orgs, company] if o]


@dataclass(slots=True)
class _Signals:
    names: set[str] = field(default_factory=set)
    orcid: set[str] = field(default_factory=set)
    github: set[str] = field(default_factory=set)
    domains: set[str] = field(default_factory=set)
    orgs: list[str] = field(default_factory=list)
    locations: set[str] = field(default_factory=set)


def signals(h: Hit) -> _Signals:
    s = _Signals()
    p: dict[str, Any] = h.payload
    name = p.get("name") or (h.title if h.kind == "profile" else None)
    if name:
        s.names.add(str(name))
    if p.get("orcid"):
        m = _ORCID.search(str(p["orcid"]))
        if m:
            s.orcid.add(m.group(1))
    if h.source is SourceName.GITHUB and p.get("login"):
        s.github.add(str(p["login"]).lower())
    for candidate in (h.url, p.get("blog"), p.get("homepage")):
        if not candidate:
            continue
        m = _GITHUB_PROFILE.match(str(candidate))
        if m:
            s.github.add(m.group(1).lower())
    for candidate in (p.get("blog"), p.get("homepage")):
        domain = personal_domain(str(candidate) if candidate else None)
        if domain:
            s.domains.add(domain)
    s.orgs = _orgs(h)
    if p.get("location"):
        s.locations.add(fold(str(p["location"])))
    return s


@dataclass(slots=True)
class _Cluster:
    hits: list[Hit]
    sig: _Signals
    strength: float = 0.0

    @property
    def sources(self) -> set[SourceName]:
        return {h.source for h in self.hits}

    def absorb(self, other: _Cluster, score: float) -> None:
        self.hits.extend(other.hits)
        self.sig.names |= other.sig.names
        self.sig.orcid |= other.sig.orcid
        self.sig.github |= other.sig.github
        self.sig.domains |= other.sig.domains
        self.sig.orgs.extend(other.sig.orgs)
        self.sig.locations |= other.sig.locations
        self.strength = min(1.0, self.strength + other.strength + score)


def merge_score(a: _Signals, b: _Signals) -> float:
    """Weighted sum over matched signals. Conflicting strong identifiers veto the merge."""
    if a.orcid and b.orcid and not a.orcid & b.orcid:
        return 0.0
    if a.github and b.github and not a.github & b.github:
        return 0.0
    score = 0.0
    if a.orcid & b.orcid:
        score += WEIGHTS["orcid"]
    if a.github & b.github:
        score += WEIGHTS["github"]
    if a.domains & b.domains:
        score += WEIGHTS["domain"]
    if any(names_match(x, y) for x in a.names for y in b.names):
        score += WEIGHTS["name"]
        if orgs_overlap(a.orgs, b.orgs):
            score += WEIGHTS["name_org"]
        if (
            a.locations
            and b.locations
            and any(x in y or y in x for x in a.locations for y in b.locations)
        ):
            score += WEIGHTS["name_location"]
    return round(score, 4)


def _can_merge(a: _Cluster, b: _Cluster) -> float:
    if a.sources & b.sources:
        return 0.0  # two records from one source are two people unless deduped upstream
    score = merge_score(a.sig, b.sig)
    return score if score >= MERGE_THRESHOLD else 0.0


def _cluster(seeds: list[_Cluster]) -> list[_Cluster]:
    clusters = list(seeds)
    merged = True
    while merged:
        merged = False
        best: tuple[float, int, int] | None = None
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                score = _can_merge(clusters[i], clusters[j])
                if score and (best is None or score > best[0]):
                    best = (score, i, j)
        if best:
            score, i, j = best
            clusters[i].absorb(clusters.pop(j), score)
            merged = True
    return clusters


def _display_name(c: _Cluster) -> str:
    preferred = [
        h for h in c.hits if h.kind == "profile" and h.source in (SourceName.EXA, SourceName.GITHUB)
    ]
    names = [str(h.payload.get("name") or h.title) for h in (preferred or c.hits)]
    counts = Counter(n for n in names if n)
    # Most common, then longest (prefer "Geoffrey E. Hinton" over "G. Hinton").
    return max(counts, key=lambda n: (counts[n], len(n))) if counts else ""


def _handles(c: _Cluster) -> dict[str, str]:
    handles: dict[str, str] = {}
    for h in c.hits:
        p = h.payload
        if h.source is SourceName.GITHUB and p.get("login"):
            handles.setdefault("github", str(p["login"]))
        if p.get("twitter_username"):
            handles.setdefault("x", str(p["twitter_username"]))
        if p.get("openalex_id"):
            handles.setdefault("openalex", str(p["openalex_id"]))
        if p.get("author_id"):
            handles.setdefault("semantic_scholar", str(p["author_id"]))
        if h.source is SourceName.YOUTUBE and h.kind == "profile" and p.get("channel_id"):
            handles.setdefault("youtube", str(p["channel_id"]))
    if c.sig.orcid:
        handles["orcid"] = sorted(c.sig.orcid)[0]
    if c.sig.domains:
        handles["website"] = sorted(c.sig.domains)[0]
    return handles


def _to_entity(c: _Cluster, q: SourceQuery | None) -> Entity:
    best = max((relevance(h, q) for h in c.hits), default=0.0) if q else 0.0
    score = min(1.0, 0.4 * min(best, 1.5) / 1.5 + 0.15 * len(c.sources) + 0.3 * c.strength)
    return Entity(
        display_name=_display_name(c),
        handles=_handles(c),
        claim_count=len(c.hits),
        score=round(score, 4),
        hits=list(c.hits),
    )


def _entity_cluster(e: Entity) -> _Cluster:
    sig = _Signals()
    for h in e.hits:
        s = signals(h)
        sig.names |= s.names
        sig.orcid |= s.orcid
        sig.github |= s.github
        sig.domains |= s.domains
        sig.orgs.extend(s.orgs)
        sig.locations |= s.locations
    return _Cluster(hits=list(e.hits), sig=sig)


def attach_content(entities: list[Entity], content: list[Hit]) -> list[Entity]:
    """Attach articles, episodes, videos, and repos to the entity they name or belong to."""
    out: list[Entity] = []
    claimed: set[str] = set()
    for e in entities:
        github = e.handles.get("github", "").lower()
        extra: list[Hit] = []
        for h in content:
            if h.url in claimed:
                continue
            owner = str(h.payload.get("owner_login") or "").lower()
            if (github and owner == github) or (
                e.display_name and name_in_text(e.display_name, f"{h.title} {h.snippet}")
            ):
                extra.append(h)
                claimed.add(h.url)
        out.append(replace(e, hits=[*e.hits, *extra], claim_count=e.claim_count + len(extra)))
    return out


def resolve_identity(hits: list[Hit], q: SourceQuery | None = None) -> list[Entity]:
    """Profile hits seed entities and merge under the two-source rule; content hits attach."""
    profiles = [h for h in hits if h.kind == "profile"]
    content = [h for h in hits if h.kind != "profile"]
    clusters = _cluster([_Cluster(hits=[h], sig=signals(h)) for h in profiles])
    entities = sorted((_to_entity(c, q) for c in clusters), key=lambda e: e.score, reverse=True)
    return attach_content(entities, content)


def merge_entities(entities: list[Entity], q: SourceQuery | None = None) -> list[Entity]:
    clusters = _cluster([_entity_cluster(e) for e in entities])
    return sorted((_to_entity(c, q) for c in clusters), key=lambda e: e.score, reverse=True)


def pipeline(hits: list[Hit], q: SourceQuery) -> list[Entity]:
    return resolve_identity(rank(dedupe(normalize(hits)), q), q)
