"""iTunes Search: episode lookup via the undocumented `entity=podcastEpisode` recipe.

Keyless. Throttled to 15 calls per 10 seconds in core.http (research/07-api-recipes.md).
"""

from __future__ import annotations

from core.cache import TTL_IMMUTABLE
from core.http import HttpClient, get_client
from core.models import Hit, SourceName, SourceQuery
from core.sources.base import BaseSource, make_hit, register

API = "https://itunes.apple.com/search"


@register
class ITunes(BaseSource):
    name = SourceName.ITUNES
    requires_key = False
    returns = "Apple Podcasts episodes whose title or description matches the person"

    def _search(self, q: SourceQuery) -> list[Hit]:
        data = self.http.get(
            self.name,
            API,
            params={"term": q.text, "entity": "podcastEpisode", "limit": min(q.limit, 50)},
        ).json()
        return [
            make_hit(
                self.name,
                "episode",
                r["trackViewUrl"],
                r.get("trackName") or "",
                r.get("shortDescription") or r.get("description") or "",
                {"show": r.get("collectionName"), "published": r.get("releaseDate")},
                q.text,
            )
            for r in data.get("results", [])
            if r.get("trackViewUrl")
        ]


def resolve_episode(title: str, http: HttpClient | None = None) -> str | None:
    """Resolve an Apple Podcasts episode URL from an episode title (two-step podcast pattern)."""
    try:
        data = (
            (http or get_client())
            .get(
                "itunes",
                API,
                params={"term": title, "entity": "podcastEpisode", "limit": 1},
                ttl=TTL_IMMUTABLE,
            )
            .json()
        )
    except Exception:
        return None
    results = data.get("results") or []
    url = results[0].get("trackViewUrl") if results else None
    return url if isinstance(url, str) else None
