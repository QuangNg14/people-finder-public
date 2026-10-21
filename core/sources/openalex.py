"""OpenAlex: authors, institutions, h-index, ORCID. Keyless; `mailto` joins the polite pool."""

from __future__ import annotations

from datetime import date
from typing import Any

from core.cache import TTL_PROFILE, TTL_SEARCH
from core.models import Hit, SourceName, SourceQuery
from core.sources.base import BaseSource, make_hit, register

API = "https://api.openalex.org/authors"
WORKS = "https://api.openalex.org/works"
WORK_FIELDS = "id,doi,display_name,publication_date,primary_location,cited_by_count"


@register
class OpenAlex(BaseSource):
    name = SourceName.OPENALEX
    requires_key = False
    key_env = ("OPENALEX_EMAIL",)
    returns = "Researcher profiles: ORCID, h-index, works and citation counts, institutions, topics"

    def missing_keys(self) -> list[str]:
        return []  # the email is optional; it only selects the polite pool

    def _params(self, extra: dict[str, Any]) -> dict[str, Any]:
        email = self.key()
        return {**extra, **({"mailto": email} if email else {})}

    def _search(self, q: SourceQuery) -> list[Hit]:
        if not q.person:
            return []  # author search on a free-text description is noise, not discovery
        data = self.http.get(
            self.name,
            API,
            params=self._params({"search": q.person, "per_page": min(q.limit, 25)}),
            ttl=TTL_PROFILE,
        ).json()
        return [self._hit(a, q.person) for a in data.get("results", []) if a.get("id")]

    def _hit(self, a: dict[str, Any], provenance: str) -> Hit:
        stats = a.get("summary_stats") or {}
        institutions = [i.get("display_name") for i in a.get("last_known_institutions") or [] if i]
        topics = [t.get("display_name") for t in (a.get("topics") or [])[:5]]
        return make_hit(
            self.name,
            "profile",
            a["id"],
            a.get("display_name") or "",
            ", ".join(i for i in institutions if i),
            {
                "openalex_id": a["id"].rsplit("/", 1)[-1],
                "name": a.get("display_name"),
                "orcid": a.get("orcid"),
                "h_index": stats.get("h_index"),
                "works_count": a.get("works_count"),
                "cited_by_count": a.get("cited_by_count"),
                "institutions": [i for i in institutions if i],
                "orgs": [i for i in institutions if i],
                "topics": [t for t in topics if t],
            },
            provenance,
        )

    def _fetch(self, ref: str) -> Hit | None:
        author_id = ref.rsplit("/", 1)[-1]
        a = self.http.get(self.name, f"{API}/{author_id}", params=self._params({})).json()
        return self._hit(a, ref) if a.get("id") else None

    def works_by_author(
        self, author_id: str, since: date | None = None, limit: int = 10
    ) -> list[Hit]:
        """Works by one author, newest first. May raise; callers isolate."""
        aid = author_id.rstrip("/").rsplit("/", 1)[-1]
        filt = f"author.id:{aid}" + (f",from_publication_date:{since.isoformat()}" if since else "")
        data = self.http.get(
            self.name,
            WORKS,
            params=self._params(
                {
                    "filter": filt,
                    "sort": "publication_date:desc",
                    "per_page": min(limit, 50),
                    "select": WORK_FIELDS,
                }
            ),
            ttl=TTL_SEARCH,
        ).json()
        hits: list[Hit] = []
        for w in data.get("results", []):
            url = w.get("doi") or w.get("id")
            if not isinstance(url, str) or not url.startswith("http"):
                continue
            venue = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
            hits.append(
                make_hit(
                    self.name,
                    "publication",
                    url,
                    w.get("display_name") or "",
                    venue or "",
                    {
                        "published": w.get("publication_date"),
                        "venue": venue,
                        "cited_by_count": w.get("cited_by_count"),
                        "openalex_work_id": str(w.get("id", "")).rsplit("/", 1)[-1],
                        "author_id": aid,
                    },
                    f"works by {aid}",
                )
            )
        return hits
