"""TinyFish news search: the default news route at $0.00/call (D7)."""

from __future__ import annotations

from core.models import Hit, SourceName, SourceQuery
from core.sources.base import BaseSource, make_hit, register

API = "https://api.search.tinyfish.ai"


@register
class TinyFishNews(BaseSource):
    name = SourceName.TINYFISH_NEWS
    requires_key = True
    key_env = ("TINYFISH_API_KEY",)
    returns = "News articles with publisher and date"

    def _search(self, q: SourceQuery) -> list[Hit]:
        query = f'"{q.person}"' if q.person else q.text
        if q.org:
            query += f" {q.org}"
        params: dict[str, object] = {"query": query, "domain_type": "news"}
        if q.location and len(q.location) == 2:
            params["location"] = q.location.upper()
        if q.since:
            params["after_date"] = q.since.strftime("%Y-%m-%d")
        data = self.http.get(
            self.name, API, params=params, headers={"X-API-Key": self.key() or ""}
        ).json()
        return [
            make_hit(
                self.name,
                "article",
                r["url"],
                r.get("title") or "",
                r.get("snippet") or "",
                {
                    "published": r.get("date"),
                    "publisher": r.get("publisher"),
                    "domain": r.get("site_name"),
                },
                query,
            )
            for r in data.get("results", [])
            if r.get("url")
        ]
