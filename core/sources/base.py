"""The Source contract and registry (spec section 6).

Only sources in SOURCES are reachable from any tool call. Adding a source is one file plus the
`@register` decorator on its class.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar, Literal, Protocol, runtime_checkable

from core.config import env
from core.http import HttpClient, SourceError, get_client
from core.models import Hit, SourceName, SourceQuery, utcnow

log = logging.getLogger("people_finder.sources")

Status = Literal["ok", "empty", "missing_key", "error"]


@runtime_checkable
class Source(Protocol):
    name: SourceName
    requires_key: bool

    def search(self, q: SourceQuery) -> list[Hit]: ...
    def fetch(self, ref: str) -> Hit | None: ...


@dataclass(frozen=True, slots=True)
class SourceOutcome:
    source: SourceName
    hits: list[Hit] = field(default_factory=list)
    status: Status = "ok"
    detail: str = ""

    @property
    def footer(self) -> str:
        return f"{self.source}: {self.status}" + (f" ({self.detail})" if self.detail else "")


class BaseSource(ABC):
    """Isolation lives here: a failing or unkeyed source returns [] and never raises (D18)."""

    name: ClassVar[SourceName]
    requires_key: ClassVar[bool] = False
    key_env: ClassVar[tuple[str, ...]] = ()
    returns: ClassVar[str] = ""

    def __init__(self, http: HttpClient | None = None) -> None:
        self._http = http

    @property
    def http(self) -> HttpClient:
        return self._http or get_client()

    def key(self, name: str | None = None) -> str | None:
        return env(name or self.key_env[0]) if (name or self.key_env) else None

    def missing_keys(self) -> list[str]:
        return [k for k in self.key_env if env(k) is None] if self.requires_key else []

    def run(self, q: SourceQuery) -> SourceOutcome:
        missing = self.missing_keys()
        if missing:
            return SourceOutcome(self.name, [], "missing_key", "set " + ", ".join(missing))
        try:
            hits = self._search(q)
        except SourceError as exc:
            log.warning("%s failed: %s", self.name, exc)
            return SourceOutcome(self.name, [], "error", str(exc))
        except Exception as exc:  # malformed payloads must not fail the dossier
            log.warning("%s raised %s", self.name, type(exc).__name__)
            return SourceOutcome(self.name, [], "error", type(exc).__name__)
        return SourceOutcome(self.name, hits, "ok" if hits else "empty")

    def search(self, q: SourceQuery) -> list[Hit]:
        return self.run(q).hits

    def fetch(self, ref: str) -> Hit | None:
        if self.missing_keys():
            return None
        try:
            return self._fetch(ref)
        except Exception as exc:
            log.warning("%s fetch failed: %s", self.name, type(exc).__name__)
            return None

    @abstractmethod
    def _search(self, q: SourceQuery) -> list[Hit]: ...

    def _fetch(self, ref: str) -> Hit | None:
        return None


def make_hit(
    source: SourceName,
    kind: str,
    url: str,
    title: str,
    snippet: str,
    payload: dict[str, object],
    provenance: str,
) -> Hit:
    return Hit(
        source=source,
        kind=kind,
        url=url,
        title=(title or "").strip(),
        snippet=" ".join((snippet or "").split())[:500],
        retrieved_at=utcnow(),
        payload={k: v for k, v in payload.items() if v not in (None, "", [], {})},
        provenance=provenance,
    )


SOURCES: dict[SourceName, BaseSource] = {}


def register[T: BaseSource](cls: type[T]) -> type[T]:
    SOURCES[cls.name] = cls()
    return cls


def describe_sources() -> list[dict[str, object]]:
    """What list_sources reports: name, what it returns, key requirement, key presence."""
    out: list[dict[str, object]] = []
    for name, src in SOURCES.items():
        out.append(
            {
                "name": str(name),
                "returns": src.returns,
                "requires_key": src.requires_key,
                "key_env": list(src.key_env),
                "key_present": all(env(k) is not None for k in src.key_env)
                if src.key_env
                else None,
                "available": not src.missing_keys(),
            }
        )
    return out
