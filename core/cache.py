"""SQLite TTL cache of raw provider responses. The only persistence (spec section 9, D4)."""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS http_cache (
    cache_key   TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    body        BLOB NOT NULL,
    fetched_at  INTEGER NOT NULL,
    ttl_seconds INTEGER NOT NULL,
    status      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_http_cache_source_time ON http_cache(source, fetched_at);
"""

TTL_PROFILE = 24 * 3600
TTL_SEARCH = 6 * 3600
TTL_IMMUTABLE = 7 * 24 * 3600


@dataclass(frozen=True, slots=True)
class CacheEntry:
    body: bytes
    status: int
    fetched_at: int
    ttl_seconds: int

    def fresh(self, now: float | None = None) -> bool:
        return (now if now is not None else time.time()) < self.fetched_at + self.ttl_seconds


class Cache:
    def __init__(self, path: Path | str = ":memory:") -> None:
        if isinstance(path, Path):
            path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)

    def get(self, key: str, *, allow_stale: bool = False) -> CacheEntry | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT body, status, fetched_at, ttl_seconds FROM http_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        entry = CacheEntry(body=row[0], status=row[1], fetched_at=row[2], ttl_seconds=row[3])
        if entry.fresh() or allow_stale:
            return entry
        return None

    def put(self, key: str, source: str, body: bytes, status: int, ttl_seconds: int) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO http_cache"
                " (cache_key, source, body, fetched_at, ttl_seconds, status)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (key, source, body, int(time.time()), ttl_seconds, status),
            )
            self._conn.commit()

    def purge_expired(self, grace_seconds: int = 7 * 24 * 3600) -> int:
        """Delete entries expired for longer than the grace window kept for 429 fallback."""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM http_cache WHERE fetched_at + ttl_seconds + ? < ?",
                (grace_seconds, int(time.time())),
            )
            self._conn.commit()
            return cur.rowcount

    def close(self) -> None:
        with self._lock:
            self._conn.close()
