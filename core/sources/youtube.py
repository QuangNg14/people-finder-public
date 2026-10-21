"""YouTube Data API v3: channels and videos. 100 quota units per search call."""

from __future__ import annotations

from core.cache import TTL_PROFILE
from core.models import Hit, SourceName, SourceQuery
from core.sources.base import BaseSource, make_hit, register

API = "https://www.googleapis.com/youtube/v3/search"
CHANNELS_API = "https://www.googleapis.com/youtube/v3/channels"
PLAYLIST_ITEMS_API = "https://www.googleapis.com/youtube/v3/playlistItems"


@register
class YouTube(BaseSource):
    name = SourceName.YOUTUBE
    requires_key = True
    key_env = ("YOUTUBE_API_KEY",)
    returns = "YouTube channels (kind=profile) and videos (kind=video) matching a person"

    def _search(self, q: SourceQuery) -> list[Hit]:
        params: dict[str, object] = {
            "part": "snippet",
            "q": q.text,
            "type": "channel,video",
            "maxResults": min(q.limit, 50),
            "key": self.key() or "",
        }
        if q.since:
            params["publishedAfter"] = q.since.isoformat().replace("+00:00", "Z")
        # The key travels as a query parameter; core.http drops it from the cache key.
        data = self.http.get(self.name, API, params=params).json()
        hits: list[Hit] = []
        for item in data.get("items", []):
            ident = item.get("id") or {}
            sn = item.get("snippet") or {}
            if ident.get("kind") == "youtube#channel" and ident.get("channelId"):
                url = f"https://www.youtube.com/channel/{ident['channelId']}"
                kind = "profile"
            elif ident.get("kind") == "youtube#video" and ident.get("videoId"):
                url = f"https://www.youtube.com/watch?v={ident['videoId']}"
                kind = "video"
            else:
                continue
            hits.append(
                make_hit(
                    self.name,
                    kind,
                    url,
                    sn.get("title") or "",
                    sn.get("description") or "",
                    {
                        "channel_id": sn.get("channelId"),
                        "channel_title": sn.get("channelTitle"),
                        "published_at": sn.get("publishedAt"),
                        "name": sn.get("channelTitle") if kind == "profile" else None,
                    },
                    q.text,
                )
            )
        return hits

    def channel_uploads(self, channel_id: str, limit: int = 10) -> list[Hit]:
        """Recent uploads via the channel's uploads playlist (2 quota units, not 100). May raise."""
        key = self.key() or ""
        channels = self.http.get(
            self.name,
            CHANNELS_API,
            params={"part": "contentDetails", "id": channel_id, "key": key},
            ttl=TTL_PROFILE,
        ).json()
        items = channels.get("items") or []
        uploads = (
            ((items[0].get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads")
            if items
            else None
        )
        if not uploads:
            return []
        data = self.http.get(
            self.name,
            PLAYLIST_ITEMS_API,
            params={
                "part": "snippet,contentDetails",
                "playlistId": uploads,
                "maxResults": min(limit, 50),
                "key": key,
            },
        ).json()
        hits: list[Hit] = []
        for item in data.get("items", []):
            details = item.get("contentDetails") or {}
            sn = item.get("snippet") or {}
            video_id = details.get("videoId")
            if not video_id:
                continue
            hits.append(
                make_hit(
                    self.name,
                    "video",
                    f"https://www.youtube.com/watch?v={video_id}",
                    sn.get("title") or "",
                    sn.get("description") or "",
                    {
                        "published": details.get("videoPublishedAt"),
                        "channel_id": channel_id,
                        "show": sn.get("channelTitle"),
                    },
                    f"uploads of {channel_id}",
                )
            )
        return hits
