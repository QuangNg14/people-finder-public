"""GDELT 2.0 DOC API: long-tail global news mentions. Keyless, 1 request per 5 seconds."""

from __future__ import annotations

import json

from core.http import SourceError
from core.models import Hit, SourceName, SourceQuery
from core.sources.base import BaseSource, make_hit, register

API = "https://api.gdeltproject.org/api/v2/doc/doc"


@register
class Gdelt(BaseSource):
    name = SourceName.GDELT
    requires_key = False
    returns = "Global news articles mentioning the person (with domain, language, country)"

    def _search(self, q: SourceQuery) -> list[Hit]:
        query = f'"{q.person}"' if q.person else q.text
        if q.org and q.person:
            query += f' "{q.org}"'
        params: dict[str, object] = {
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": min(q.limit, 75),
            "sort": "datedesc",
        }
        if q.since:
            params["startdatetime"] = q.since.strftime("%Y%m%d%H%M%S")
        result = self.http.get(self.name, API, params=params)
        try:
            data = result.json()
        except json.JSONDecodeError as exc:
            # GDELT answers malformed queries with a plain-text explanation and a 200.
            raise SourceError(self.name, "non-JSON response") from exc
        articles = sorted(
            (a for a in data.get("articles", []) if a.get("url")),
            key=lambda a: a.get("seendate", ""),
            reverse=True,
        )
        return [
            make_hit(
                self.name,
                "article",
                a["url"],
                a.get("title") or "",
                "",
                {
                    "published": a.get("seendate"),
                    "domain": a.get("domain"),
                    "language": a.get("language"),
                    "country": a.get("sourcecountry"),
                },
                query,
            )
            for a in articles
        ]
