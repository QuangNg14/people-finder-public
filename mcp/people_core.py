"""people-core MCP server: discover, dossier, find_handle, list_sources. Official APIs only.

Register (servers load at session startup, so restart after registering; on Windows use forward
slashes in the path):

    claude mcp add-json people-core -s user '{"type":"stdio","command":"uv","args":["run",
      "--directory","<repo>","python","mcp/people_core.py"]}'
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from core.api import (
    discover_json,
    dossier_json,
    find_handle_json,
    footprint_page_text,
    list_sources_json,
    whats_new_json,
)

server = FastMCP(
    "people-core",
    instructions=(
        "Cited people search over public, official APIs. Every claim carries a source_url. "
        "Discovery only: never contact, connect with, or message anyone on the user's behalf. "
        "Read the footer: it names sources that were unavailable, so a missing field is explained."
    ),
)


@server.tool
def dossier(
    person: str, org: str | None = None, location: str | None = None, limit: int = 10
) -> dict[str, Any]:
    """Per-field cited dossier for one person, by name or GitHub handle.

    `org` and `location` corroborate identity. Same-name people are returned separately in
    `other_people_with_this_name`, never merged.
    """
    return dossier_json(person, org, location, limit)


@server.tool
def discover(
    description: str, location: str | None = None, org: str | None = None, limit: int = 20
) -> dict[str, Any]:
    """Ranked candidate people matching a natural-language description, each with evidence."""
    return discover_json(description, location, org, limit)


@server.tool
def find_handle(person: str, platform: str | None = None, org: str | None = None) -> dict[str, Any]:
    """Public handles (GitHub, X, ORCID, website, YouTube) for one person, each with its source."""
    return find_handle_json(person, platform, org)


@server.tool
def list_sources() -> list[dict[str, object]]:
    """Every source: what it returns, whether a key is required, and whether it is present now."""
    return list_sources_json()


@server.tool
def footprint_page(
    person: str, org: str | None = None, location: str | None = None, limit: int = 10
) -> str:
    """Alias-style Markdown page of a person's papers, talks, videos, writing and code.

    Every item links to its source; same-name people are listed separately. Nothing is stored.
    """
    return footprint_page_text(person, org, location, limit)


@server.tool
def whats_new(people: list[dict[str, Any]], since: str, limit: int = 10) -> dict[str, Any]:
    """New items from followed people since a date (YYYY-MM-DD). Pull-based; nothing is stored.

    Each person is {"name": ..., optional "openalex", "semantic_scholar", "github",
    "youtube_channel", "podcasts": bool, "news": bool}. `published` items carry a provider
    publication date; `newly_observed` items only an observation date or none.
    """
    return whats_new_json(people, since, limit)


if __name__ == "__main__":
    server.run()
