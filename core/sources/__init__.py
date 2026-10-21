"""Importing this package registers every core source in SOURCES."""

from core.sources import (
    exa,
    gdelt,
    github,
    itunes,
    openalex,
    podcast_index,
    semantic_scholar,
    tinyfish,
    youtube,
)
from core.sources.base import SOURCES, BaseSource, Source, SourceOutcome, describe_sources

__all__ = [
    "SOURCES",
    "BaseSource",
    "Source",
    "SourceOutcome",
    "describe_sources",
    "exa",
    "gdelt",
    "github",
    "itunes",
    "openalex",
    "podcast_index",
    "semantic_scholar",
    "tinyfish",
    "youtube",
]
