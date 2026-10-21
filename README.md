# people-finder

A people-search and networking engine: given a person or a description of the kind of person you
want, return a **structured, per-field cited** result, over public sources, with **no stored
database of people**.

All phases of [`docs/roadmap.md`](docs/roadmap.md) are implemented: the product-safe core, all
nine core sources, identity resolution, both planners, the `people-core` MCP server, the
and the consented-directory schemas. The dev/test-only `instrument/` layer described in the docs is
not part of this public repository.

**Start here:** [`docs/superpowers/specs/2026-10-14-people-finder-design.md`](/docs/superpowers/specs/2026-10-14-people-finder-design.md)

---

## Status

| Piece | State |
|---|---|
| Problem definition, scope, non-goals | done |
| Architecture (core / instrument split) | done |
| Data model and the citation invariant | done |
| Source selection, with cost verified per source | done |
| Legal and ToS boundary analysis | done |
| Every candidate vendor evaluated and decided | done |
| Prior art teardown (Alias 2021, job crawler) | done |
| Implementation roadmap with acceptance criteria | done |
| Core: models, citation invariant, cache, HTTP client (phases 0 to 1) | done |
| Core sources: GitHub, Exa, OpenAlex, Semantic Scholar, YouTube, Podcast Index, iTunes, GDELT, TinyFish (phases 2 to 4) | done, offline-tested; keyed sources not yet live-verified |
| Resolution, dossier, discovery (phases 5 to 7) | done |
| `people-core` MCP server (phase 8) | done, not yet registered in a Claude session |
| `instrument/` layer (phase 9): LinkedIn, Instagram, X, Reddit, transcripts | done, dev/test only; transcripts live-verified, others offline-tested |
| Consented-directory schemas (phase 10) | done |
| Follow, "what's new since" (phase 11, Alias revival) | done; OpenAlex/GitHub/GDELT live-verified keyless |
| Footprint page, Alias-style Markdown (phase 12) | done; live-verified on GitHub + OpenAlex |
| Claimed pages, opt-in "ask my work" (phases 13-14) | proposals, see `docs/research/08-alias-revival-2026-10.md` |

## Usage

```bash
uv sync
cp .env.example .env            # fill in the keys you have; every source degrades without one
uv run python -m core sources   # which sources are available right now
uv run python -m core dossier "Geoffrey Hinton" --org "University of Toronto"
uv run python -m core discover "developer tooling founders" --location Vietnam
uv run python -m core handle torvalds --platform github
uv run python -m core page torvalds                      # Markdown page to stdout
uv run python -m core page torvalds --out torvalds.md    # explicit local export
uv run python -m core whats-new --since 2026-09-01 --name "Geoffrey Hinton" --openalex A5108093963
uv run python -m core whats-new --since 2026-09-01 --watchlist watchlist.toml
```

`dossier`, `discover`, `handle`, `whats-new` and `sources` print JSON; `page` prints Markdown. Each
claim carries `source_url`; `footer` names every source that was unavailable or empty, and
`other_people_with_this_name` lists same-name people that were deliberately not merged.

`whats-new` splits results into `published` (the provider gives a publication date on or after
`--since`) and `newly_observed` (GDELT observation dates, or no usable date). Items with
`match: "identifier"` came from the person's own OpenAlex, Semantic Scholar, GitHub or YouTube
identifier; `match: "name"` items may belong to a same-name person. A watchlist is a TOML file you
own:

```toml
[[person]]
name = "Geoffrey Hinton"
openalex = "A5108093963"

[[person]]
name = "Linus Torvalds"
github = "torvalds"
news = false        # skip TinyFish/GDELT name search
```

Nothing polls: schedule `whats-new` yourself if you want a digest.

The MCP server exposes the same operations as tools (`dossier`, `discover`, `find_handle`,
`list_sources`, `footprint_page`, `whats_new`):

```bash
claude mcp add-json people-core -s user \
  '{"type":"stdio","command":"uv","args":["run","--directory","<repo path, forward slashes>","python","mcp/people_core.py"]}'
```

Restart the session after registering. The raw-response cache lives at
`~/.cache/people-finder/http_cache.sqlite` (override with `PEOPLE_FINDER_CACHE`).

Every phase gate: `uv run ruff check . && uv run mypy && uv run pytest`. Tests use recorded or
spec-shaped fixtures under `tests/fixtures/` and need no network.

**Behind a TLS-inspecting proxy** (for example a corporate network where `files.pythonhosted.org`
is blocked), point uv at the approved mirror for that shell only, rather than writing it into
`pyproject.toml`: `UV_DEFAULT_INDEX=<mirror> UV_NATIVE_TLS=1 uv sync`.

### Instrument layer

The design keeps scrapers for platforms whose terms forbid automated access in a separate,
dev/test-only `instrument/` layer that `core/` can never import. That layer is not published here.

## The thesis in one paragraph

The people-search market splits into stored scraped databases (Apollo, RocketReach, Proxycurl) and
unstructured search engines. The first is a legal liability with a defined end state, and Proxycurl
reached that end state in July 2025. The second returns links with no identity resolution and no
per-field citations. This project takes the third position: **retrieve and cite public sources on
demand, hold no person database, and make uncited output structurally impossible.** A shipped
product would add exactly one thing, a consented directory where the person supplies their own
detail, because Facebook, WhatsApp, and Instagram handles only ever come from the person. The
retrieval core is deliberately built so that shipping is an addition, not a rewrite.

At personal volume the product-safe core costs **$0.00/month**.

## Repository layout

```
people-finder/
├── README.md                    this file
├── .env.example                 key NAMES only, never values
├── docs/
│   ├── 00-index.md              navigation, read order
│   ├── roadmap.md               phased build order, acceptance criteria per phase
│   ├── decisions.md             every decision, with the alternatives that were rejected
│   ├── open-questions.md        what is still unresolved, and what is deliberately deferred
│   ├── research/
│   │   ├── 01-platform-reality.md    can you search a person's content per platform
│   │   ├── 02-legal-boundaries.md    LinkedIn, Meta, hiQ, Proxycurl, GDPR, Decree 13
│   │   ├── 03-source-evaluation.md   every candidate source, priced, with a verdict
│   │   ├── 04-github-landscape.md    the OSINT repo survey and GitHub account verdicts
│   │   ├── 05-prior-art-alias.md     what Alias was, what survives it, what to leave behind
│   │   ├── 06-prior-art-job-crawler.md  the patterns to port from Discord-Job-Crawl-Server
│   │   └── 07-api-recipes.md         working API recipes recovered from the 2021 prototype
│   └── superpowers/
│       └── specs/2026-10-14-people-finder-design.md   the master design
└── (code, to be created per docs/roadmap.md)
```

## Resuming on another machine

Read in this order. The design doc is self-contained, but the research and decisions docs are what
make the design defensible rather than arbitrary.

1. `docs/00-index.md` for navigation.
2. `docs/superpowers/specs/2026-10-14-people-finder-design.md` for the design.
3. `docs/decisions.md` before changing anything in the design. Most of what looks like a missing feature is a decision that was made deliberately.
4. `docs/roadmap.md` for the build order.

Environment, on the implementing machine:

```bash
# Python 3.13 and uv. On macOS:
brew install uv
# On Windows:
winget install astral-sh.uv
uv python install 3.13
```

Then, per phase 1 of `docs/roadmap.md`:

```bash
cd "/path/to/people-finder"
uv init --python 3.13
uv add httpx pydantic fastmcp
uv add --dev pytest respx ruff mypy
uv run pytest
```

## Keys

Names only, in `.env`. Never commit values, never put them in the Obsidian vault, never in
`handoffs/.env`.

| Variable | Needed for | Cost |
|---|---|---|
| `EXA_API_KEY` | the spine source, `category:"people"` | free under the $10/month credit |
| `TINYFISH_API_KEY` | default news route | free |
| `GITHUB_TOKEN` | GitHub source at volume | free |
| `YOUTUBE_API_KEY` | video and channel source | free |
| `PODCAST_INDEX_KEY` + `PODCAST_INDEX_SECRET` | podcast appearances | free |
| `OPENALEX_EMAIL` | polite pool, not a key | free |
| `SEMANTIC_SCHOLAR_API_KEY` | papers, papers complement | free |

Only `EXA_API_KEY` is load-bearing for the core. Everything else degrades to `unavailable` and is
named in the output footer.

## Hard rules

These are not preferences. They are the reason the design has the shape it does. Full text in
section 19 of the master spec.

- **No person database.** The only persistence is a TTL cache of raw provider responses.
- **No phones, no home addresses, no private messages, no inferred sensitive traits.** Enforced by omission from the data model, not by filtering at the edges.
- **Discovery only.** Never auto-connect, never auto-send.
- **Scrapers live in `instrument/`, and `core/` cannot import them.** Enforced by a test and by packaging.
- **Never upload private source text, resumes, screenshots, or contact information to external AI services.**
- **Shortlists expire 90 days after the outreach cycle** unless the person replied.

## Provenance

This repository consolidates four separate bodies of work into one implementable design:

- The 2021 Alias codebase, a seed-stage content-aggregation startup. Its application source is unrecoverable; two podcast API recipes survive it.
- The Pathwise vault research, notably `<private vault>/Pathwise Resources/13-concept-synthesis/analyses/people-search-tooling-and-consented-directory-2026-10.md`.
- The prior finder build at `pathwise-people-finder` (Windows, 2026-10-13), now superseded.
- `Discord-Job-Crawl-Server/`, whose source-module contract, normalize/dedupe/rank layer, and deployable Docker image are the pattern donor for the core.
