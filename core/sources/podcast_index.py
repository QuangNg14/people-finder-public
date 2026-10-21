"""Podcast Index: episodes a person appears on. Free, key + secret, SHA-1 signed headers."""

from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime

from core.models import Hit, SourceName, SourceQuery
from core.sources.base import BaseSource, make_hit, register

API = "https://api.podcastindex.org/api/1.0/search/byperson"


@register
class PodcastIndex(BaseSource):
    name = SourceName.PODCAST_INDEX
    requires_key = True
    key_env = ("PODCAST_INDEX_KEY", "PODCAST_INDEX_SECRET")
    returns = "Podcast episodes where the person is a host, guest, or named in the episode"

    def _headers(self) -> dict[str, str]:
        key = self.key("PODCAST_INDEX_KEY") or ""
        secret = self.key("PODCAST_INDEX_SECRET") or ""
        now = str(int(time.time()))
        # Podcast Index mandates SHA-1 for its request signature; not a security choice here.
        digest = hashlib.sha1((key + secret + now).encode("utf-8"), usedforsecurity=False)
        return {"X-Auth-Key": key, "X-Auth-Date": now, "Authorization": digest.hexdigest()}

    def _search(self, q: SourceQuery) -> list[Hit]:
        if not q.person:
            return []
        data = self.http.get(
            self.name,
            API,
            params={"q": q.person, "max": min(q.limit, 50), "fulltext": ""},
            headers=self._headers(),
        ).json()
        hits: list[Hit] = []
        for ep in data.get("items", []):
            url = ep.get("link") or (
                f"https://podcastindex.org/podcast/{ep['feedId']}?episode={ep['id']}"
                if ep.get("feedId") and ep.get("id")
                else None
            )
            if not url or not url.startswith(("http://", "https://")):
                continue
            published = ep.get("datePublished")
            hits.append(
                make_hit(
                    self.name,
                    "episode",
                    url,
                    ep.get("title") or "",
                    ep.get("description") or "",
                    {
                        "show": ep.get("feedTitle"),
                        "published": datetime.fromtimestamp(published, UTC).isoformat()
                        if isinstance(published, int)
                        else None,
                        "feed_url": ep.get("feedUrl"),
                    },
                    q.person,
                )
            )
        return hits
