"""CLI: `uv run python -m core <dossier|discover|handle|page|whats-new|sources>`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.api import (
    discover_json,
    dossier_json,
    find_handle_json,
    footprint_page_text,
    list_sources_json,
    whats_new_from_file,
    whats_new_json,
)

IDENTIFIER_FLAGS = ("openalex", "semantic_scholar", "github", "youtube_channel")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # emoji in GitHub bios break cp1252 consoles
    parser = argparse.ArgumentParser(prog="people-finder")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_dossier = sub.add_parser("dossier", help="cited dossier for one person")
    p_dossier.add_argument("person")
    p_dossier.add_argument("--org")
    p_dossier.add_argument("--location")
    p_dossier.add_argument("--limit", type=int, default=10)

    p_discover = sub.add_parser("discover", help="candidate people matching a description")
    p_discover.add_argument("description")
    p_discover.add_argument("--location")
    p_discover.add_argument("--org")
    p_discover.add_argument("--limit", type=int, default=20)

    p_handle = sub.add_parser("handle", help="public handles for one person")
    p_handle.add_argument("person")
    p_handle.add_argument("--platform")
    p_handle.add_argument("--org")

    p_page = sub.add_parser("page", help="Alias-style footprint page (Markdown), every item cited")
    p_page.add_argument("person")
    p_page.add_argument("--org")
    p_page.add_argument("--location")
    p_page.add_argument("--limit", type=int, default=10)
    p_page.add_argument("--out", help="write to this file instead of stdout (caller export)")

    p_new = sub.add_parser("whats-new", help="new items from followed people since a date")
    p_new.add_argument("--since", required=True, help="YYYY-MM-DD")
    p_new.add_argument("--watchlist", help="TOML file with [[person]] tables")
    p_new.add_argument("--name", help="one person, instead of a watchlist")
    for flag in IDENTIFIER_FLAGS:
        p_new.add_argument("--" + flag.replace("_", "-"), dest=flag)
    p_new.add_argument("--limit", type=int, default=10)

    sub.add_parser("sources", help="list sources and key status")

    args = parser.parse_args(argv)
    if args.cmd == "page":
        text = footprint_page_text(args.person, args.org, args.location, args.limit)
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
            print(f"wrote {args.out}")
        else:
            print(text, end="")
        return 0

    result: object
    if args.cmd == "dossier":
        result = dossier_json(args.person, args.org, args.location, args.limit)
    elif args.cmd == "discover":
        result = discover_json(args.description, args.location, args.org, args.limit)
    elif args.cmd == "handle":
        result = find_handle_json(args.person, args.platform, args.org)
    elif args.cmd == "whats-new":
        if bool(args.watchlist) == bool(args.name):
            parser.error("whats-new needs exactly one of --watchlist or --name")
        if args.watchlist:
            result = whats_new_from_file(args.watchlist, args.since, args.limit)
        else:
            person = {"name": args.name} | {
                f: getattr(args, f) for f in IDENTIFIER_FLAGS if getattr(args, f)
            }
            result = whats_new_json([person], args.since, args.limit)
    else:
        result = list_sources_json()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
