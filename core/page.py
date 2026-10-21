"""Footprint page: render a Dossier as Alias-style Markdown (roadmap phase 12, D22).

A page is a rendering, not a record: this module returns text and writes nothing. Every item links
to the page that asserts it; same-name people are listed separately, never merged.
"""

from __future__ import annotations

from collections import defaultdict

from core.content import CONTENT_LABELS
from core.models import Claim, Dossier

SECTIONS: tuple[tuple[str, frozenset[str]], ...] = (
    ("Papers", frozenset({"publication"})),
    ("Talks and podcasts", frozenset({"podcast_appearance"})),
    ("Videos", frozenset({"video_appearance"})),
    ("Writing and news", frozenset({"news_mention"})),
    ("Code", frozenset({"github_repo", "github_release"})),
)
PROFILE_ORDER: tuple[str, ...] = (
    "current_role",
    "current_org",
    "past_role",
    "education",
    "affiliation",
    "location",
    "research_area",
    "notable_work",
    "h_index",
    "works_count",
    "paper_count",
    "citation_count",
    "public_repos",
    "bio",
    "website",
    "handle_github",
    "handle_orcid",
    "handle_x",
    "youtube_channel",
)
MAX_PER_SECTION = 15


def _text(value: str) -> str:
    """Escape Markdown that would break a link label or a table cell."""
    flat = " ".join(value.split())
    for ch in ("\\", "[", "]", "|", "*", "_", "`"):
        flat = flat.replace(ch, "\\" + ch)
    return flat


def _destination(url: str) -> str:
    # Inside <...> CommonMark forbids raw "<", ">" and line breaks; DOIs can contain "<" and ">".
    # Percent-encoding keeps the same target, and existing %XX escapes are left as they are.
    for raw, enc in (("<", "%3C"), (">", "%3E"), (" ", "%20"), ("\n", ""), ("\r", "")):
        url = url.replace(raw, enc)
    return url


def _link(label: str, url: str) -> str:
    return f"[{_text(label)}](<{_destination(url)}>)"


def _label(field: str) -> str:
    return field.replace("_", " ").capitalize()


def render_markdown(d: Dossier) -> str:
    by_field: dict[str, list[Claim]] = defaultdict(list)
    for c in d.claims:
        by_field[c.field].append(c)

    out: list[str] = [f"# {_text(d.entity.display_name)}", ""]
    if d.entity.handles:
        handles = ", ".join(f"{k}: `{v}`" for k, v in sorted(d.entity.handles.items()))
        out += [f"Identifiers: {handles}", ""]

    profile = [c for f in PROFILE_ORDER for c in by_field.get(f, [])]
    if profile:
        out += ["## Profile", "", "| Field | Value | Source |", "|---|---|---|"]
        out += [
            f"| {_label(c.field)} | {_text(c.value)} | {_link(str(c.source_name), c.source_url)} |"
            for c in profile
        ]
        out.append("")

    for title, fields in SECTIONS:
        items = [c for c in d.claims if c.field in fields]
        if not items:
            continue
        out += [f"## {title}", ""]
        out += [
            f"- {_link(c.value, c.source_url)} ({c.source_name})" for c in items[:MAX_PER_SECTION]
        ]
        if len(items) > MAX_PER_SECTION:
            out.append(f"- and {len(items) - MAX_PER_SECTION} more")
        out.append("")

    if not d.claims:
        out += ["No cited facts were found for this person.", ""]

    if d.alternates:
        out += ["## Not this person?", "", "Same-name people found separately (not merged):", ""]
        for e in d.alternates:
            evidence = e.hits[0] if e.hits else None
            line = f"- {_text(e.display_name)}"
            if evidence is not None:
                line += (
                    f": {_link(evidence.title or evidence.url, evidence.url)} ({evidence.source})"
                )
            out.append(line)
        out.append("")

    out += ["---", ""]
    contributing = ", ".join(str(s) for s in d.contributing) or "none"
    out.append(f"Sources that contributed: {contributing}.")
    if d.unavailable:
        detail = "; ".join(
            f"{s}: {d.source_status.get(str(s), 'no results')}" for s in d.unavailable
        )
        out.append(f"Unavailable or empty: {detail}.")
    lookups = {k: v for k, v in d.source_status.items() if k in CONTENT_LABELS}
    if lookups:
        out.append(
            "Content lookups: " + "; ".join(f"{k}: {v}" for k, v in sorted(lookups.items())) + "."
        )
    out.append(
        f"Generated {d.generated_at.isoformat(timespec='seconds')}. Every item links to its source."
    )
    return "\n".join(out) + "\n"
