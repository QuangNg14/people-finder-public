"""Environment-only configuration. Keys are read by name and never logged."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_loaded = False


def load_dotenv(path: Path | None = None) -> None:
    """Load KEY=VALUE pairs from the repo's .env without overriding the real environment."""
    global _loaded
    if _loaded:
        return
    _loaded = True
    env_file = path or REPO_ROOT / ".env"
    if not env_file.is_file():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def env(name: str) -> str | None:
    load_dotenv()
    value = os.environ.get(name, "").strip()
    return value or None


def cache_path() -> Path:
    configured = env("PEOPLE_FINDER_CACHE")
    if configured:
        return Path(configured)
    return Path.home() / ".cache" / "people-finder" / "http_cache.sqlite"
