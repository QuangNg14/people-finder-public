"""Semantic Scholar: authors with paper and citation counts. Keyless 429s fast; set a key."""

from __future__ import annotations

from datetime import date
from typing import Any

from core.cache import TTL_PROFILE, TTL_SEARCH
from core.models import Hit, SourceName, SourceQuery
from core.sources.base import BaseSource, make_hit, register

API = "https://api.semanticscholar.org/graph/v1/author/search"
PAPERS_API = "https://api.semanticscholar.org/graph/v1/author"
FIELDS = "name,url,affiliations,homepage,paperCount,citationCount,hIndex,externalIds"
PAPER_FIELDS = "title,url,year,publicationDate,venue,externalIds"
PAPER_PAGE_SIZE = 500
MAX_PAPER_PAGES = 4


@register
class SemanticScholar(BaseSource):
    name = SourceName.SEMANTIC_SCHOLAR
    requires_key = False
    key_env = ("SEMANTIC_SCHOLAR_API_KEY",)
    returns = "Author profiles: paper count, citations, h-index, affiliations, homepage, ORCID"

    def missing_keys(self) -> list[str]:
        return []  # keyless works for a handful of calls; the shared throttle protects it

    def _search(self, q: SourceQuery) -> list[Hit]:
        if not q.person:
            return []
        key = self.key()
        data = self.http.get(
            self.name,
            API,
            params={"query": q.person, "limit": min(q.limit, 100), "fields": FIELDS},
            headers={"x-api-key": key} if key else None,
            ttl=TTL_PROFILE,
        ).json()
        hits: list[Hit] = []
        for a in data.get("data", []):
            if not a.get("url"):
                continue
            external: dict[str, Any] = a.get("externalIds") or {}
            orcid = external.get("ORCID")
            affiliations = [x for x in a.get("affiliations") or [] if x]
            hits.append(
                make_hit(
                    self.name,
                    "profile",
                    a["url"],
                    a.get("name") or "",
                    ", ".join(affiliations),
                    {
                        "author_id": a.get("authorId"),
                        "name": a.get("name"),
                        "orcid": f"https://orcid.org/{orcid}" if orcid else None,
                        "h_index": a.get("hIndex"),
                        "paper_count": a.get("paperCount"),
                        "citation_count": a.get("citationCount"),
                        "affiliations": affiliations,
                        "orgs": affiliations,
                        "homepage": a.get("homepage"),
                    },
                    q.person,
                )
            )
        return hits

    def author_papers(
        self, author_id: str, limit: int = 10, since: date | None = None
    ) -> list[Hit]:
        """An author's papers, newest first, eligibility applied before `limit`. May raise.

        The endpoint has no date filter or ordering, so pages are read (up to MAX_PAPER_PAGES),
        papers older than `since` are dropped, the rest sorted newest first, then truncated.
        Undated papers are kept unless their year is before `since`; callers decide their bucket.
        """
        key = self.key()
        papers: list[dict[str, Any]] = []
        offset: int | None = 0
        pages = 0
        while offset is not None and pages < MAX_PAPER_PAGES:
            data = self.http.get(
                self.name,
                f"{PAPERS_API}/{author_id}/papers",
                params={"fields": PAPER_FIELDS, "limit": PAPER_PAGE_SIZE, "offset": offset},
                headers={"x-api-key": key} if key else None,
                ttl=TTL_SEARCH,
            ).json()
            papers.extend(p for p in data.get("data", []) if isinstance(p, dict))
            nxt = data.get("next")
            offset = nxt if isinstance(nxt, int) and nxt > offset else None
            pages += 1
        truncated = offset is not None

        def eligible(p: dict[str, Any]) -> bool:
            if since is None:
                return True
            when = parse_paper_date(p)
            if when is not None:
                return when >= since
            year = p.get("year")
            return not (isinstance(year, int) and year < since.year)

        def newest(p: dict[str, Any]) -> str:
            return str(p.get("publicationDate") or p.get("year") or "")

        hits: list[Hit] = []
        for p in sorted(filter(eligible, papers), key=newest, reverse=True)[:limit]:
            doi = (p.get("externalIds") or {}).get("DOI")
            url = f"https://doi.org/{doi}" if doi else p.get("url")
            if not isinstance(url, str) or not url.startswith("http"):
                continue
            hits.append(
                make_hit(
                    self.name,
                    "publication",
                    url,
                    p.get("title") or "",
                    p.get("venue") or "",
                    {
                        "published": p.get("publicationDate"),
                        "year": p.get("year"),
                        "venue": p.get("venue"),
                        "s2_paper_url": p.get("url"),
                        "author_id": author_id,
                        "list_truncated": truncated or None,
                    },
                    f"papers by {author_id}",
                )
            )
        return hits


def parse_paper_date(p: dict[str, Any]) -> date | None:
    raw = p.get("publicationDate")
    if not isinstance(raw, str):
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None
