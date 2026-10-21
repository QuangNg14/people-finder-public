"""Exa: the spine. `category:"people"` returns a structured person entity (D6).

`search_news` is the news fallback when TinyFish is unavailable (D7).
"""

from __future__ import annotations

from typing import Any

from core.cache import TTL_PROFILE, TTL_SEARCH
from core.models import Hit, SourceName, SourceQuery
from core.sources.base import BaseSource, make_hit, register

API = "https://api.exa.ai/search"


def _role(entry: dict[str, Any]) -> str:
    title = (entry.get("title") or "").strip()
    company = ((entry.get("company") or {}).get("name") or "").strip()
    return " at ".join(p for p in (title, company) if p)


@register
class Exa(BaseSource):
    name = SourceName.EXA
    requires_key = True
    key_env = ("EXA_API_KEY",)
    returns = "Structured person entities: name, location, work history, education, research"

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self.key() or "", "Content-Type": "application/json"}

    def _people_query(self, q: SourceQuery) -> str:
        parts = [q.text]
        if q.org:
            parts.append(q.org)
        if q.location:
            parts.append(q.location)
        return " ".join(parts)

    def _search(self, q: SourceQuery) -> list[Hit]:
        query = self._people_query(q)
        data = self.http.post(
            self.name,
            API,
            json_body={"query": query, "category": "people", "numResults": min(q.limit, 100)},
            headers=self._headers(),
            ttl=TTL_PROFILE,
        ).json()
        hits: list[Hit] = []
        for result in data.get("results", []):
            url = result.get("url")
            if not url:
                continue
            person = next(
                (e for e in result.get("entities") or [] if e.get("type") == "person"), None
            )
            props: dict[str, Any] = (person or {}).get("properties") or {}
            work = props.get("workHistory") or []
            current = [_role(w) for w in work if not ((w.get("dates") or {}).get("to"))]
            research = props.get("research") or {}
            payload: dict[str, Any] = {
                "exa_id": (person or {}).get("id") or result.get("id"),
                "name": props.get("name") or result.get("author"),
                "location": props.get("location"),
                "work_history": work,
                "education_history": props.get("educationHistory") or [],
                "research": research,
                "current_roles": [r for r in current if r],
                "orgs": [
                    (w.get("company") or {}).get("name")
                    for w in work
                    if (w.get("company") or {}).get("name")
                ],
            }
            snippet = "; ".join(payload["current_roles"]) or (result.get("text") or "")[:300]
            hits.append(
                make_hit(
                    self.name,
                    "profile",
                    url,
                    payload["name"] or result.get("title") or "",
                    snippet,
                    payload,
                    query,
                )
            )
        return hits

    def search_news(self, q: SourceQuery) -> list[Hit]:
        """Fallback news route at $0.007/call. Isolation rules match `search`."""
        if self.missing_keys():
            return []
        try:
            body: dict[str, Any] = {
                "query": self._people_query(q),
                "category": "news",
                "numResults": min(q.limit, 25),
            }
            if q.since:
                body["startPublishedDate"] = q.since.isoformat()
            data = self.http.post(
                self.name, API, json_body=body, headers=self._headers(), ttl=TTL_SEARCH
            ).json()
        except Exception:
            return []
        return [
            make_hit(
                self.name,
                "article",
                r["url"],
                r.get("title") or "",
                (r.get("text") or "")[:300],
                {"published": r.get("publishedDate"), "author": r.get("author")},
                body["query"],
            )
            for r in data.get("results", [])
            if r.get("url")
        ]
