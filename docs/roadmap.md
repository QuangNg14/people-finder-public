# Roadmap

Ten phases. Each one ends in something runnable and a verification command that either passes or
does not. Build them in order: phase 2 exists to prove the `Source` contract before eight more
sources are written against it, and phase 3 exists to prove the engine returns something worth
having before the long tail of free sources is wired up.

Every phase ends with: `uv run ruff check . && uv run mypy . && uv run pytest`.

**Status:** all phases are implemented and pass the gate. Phase 9 is gated as dev/test only
(`PEOPLE_FINDER_INSTRUMENT=dev`).

Line references are to
[`superpowers/specs/2026-10-14-people-finder-design.md`](/docs/superpowers/specs/2026-10-14-people-finder-design.md).

---

## Phase 0: Scaffold

**Deliverable:** an installable package with the toolchain configured and the boundary test failing
correctly (it should pass with an empty `instrument/`).

**Files:**
- `pyproject.toml`
- `core/__init__.py`
- `instrument/__init__.py`
- `tests/test_boundary.py`

**How:**
```bash
cd "/path/to/people-finder"
uv init --python 3.13 --lib
uv add httpx pydantic fastmcp
uv add --dev pytest respx ruff mypy
```

Configure `ruff` and `mypy --strict` in `pyproject.toml`. Exclude `instrument` from the built wheel.

**Acceptance:** `uv run pytest` passes. The boundary test from spec section 4.1 passes and would fail
if `core/` imported `instrument/` (verify by temporarily adding the import).

**Verify:** `uv run pytest tests/test_boundary.py -v`

---

## Phase 1: Models, the citation invariant, and the cache

**Deliverable:** `Hit`, `Claim`, `Entity`, `Dossier`, `SourceQuery`; the SQLite cache; the httpx
client with retries and cache integration.

**Files:**
- `core/models.py`
- `core/cache.py`
- `core/http.py`
- `tests/test_citation_invariant.py`

**How:** dataclasses for `Hit` and friends, but `Claim` gets the enforcement. Either a `@dataclass`
with `source_url: str` and no default, or a pydantic model with the field required. The test asserts
that constructing a claim without it raises. Cache schema is spec section 9, verbatim. `http.py`
owns retry, backoff, and the cache read/write path so no source implements its own.

**Acceptance:** `Claim("current_role", "CEO")` raises `TypeError` or `ValidationError`. A second
identical request in a test serves from cache with no second transport call (assert with respx call
count).

**Verify:** `uv run pytest tests/test_citation_invariant.py -v`

---

## Phase 2: The Source contract, proven with one source

**Deliverable:** the `Source` protocol, the `SOURCES` registry, and GitHub fully implemented against
it.

**Files:**
- `core/sources/base.py`
- `core/sources/github.py`
- `tests/sources/test_github.py`

**How:** `base.py` is spec section 6. Registry population by decorator so a source module is
self-contained. GitHub source covers user search, org members, and `/users/{login}` enrichment
(real name, company, location, blog, Twitter). Send `Accept-Encoding: gzip` and decompress: GitHub
descriptions carry emoji and the prior build hit this.

**Acceptance:** `github.search(SourceQuery(person="torvalds", limit=5))` returns 5 hits with real
URLs. Test is respx-mocked against a recorded response, so CI needs no network.

**Verify:** `uv run pytest tests/sources/test_github.py -v`

**Why this phase is early:** it is the contract that eight more sources get written against. Getting
it wrong here costs eight rewrites.

---

## Phase 3: The spine, Exa people

**Deliverable:** the Exa source, covering `category:"people"` and `category:"news"`.

**Files:**
- `core/sources/exa.py`
- `tests/sources/test_exa.py`

**How:** `category:"people"` returns a structured entity (name, location, `workHistory[]`,
`educationHistory[]`, `research`). Map `workHistory` and `educationHistory` entries into `Hit`
objects with `kind="profile"` and the structured data in `payload`. This is the first source whose
`payload` actually earns its place.

**Acceptance:** a live call for a well-known person returns a structured entity with non-empty
`workHistory`. Recorded fixture committed so the test runs offline.

**Verify:** `uv run pytest tests/sources/test_exa.py -v` then one live call:
```bash
uv run python -c "from core.sources.exa import Exa; print(Exa().search(__import__('core.models', fromlist=['SourceQuery']).SourceQuery(person='Paul Graham', limit=3)))"
```

---

## Phase 4: The remaining core sources

**Deliverable:** OpenAlex, Semantic Scholar, YouTube, Podcast Index, iTunes, GDELT, TinyFish. One
file each, one test each.

**Files:** `core/sources/` plus a test per source under
`tests/sources/`.

**How:** seven independent modules, so this phase parallelises. Notes that matter:
- **iTunes** uses the undocumented `entity=podcastEpisode` recipe in
  `research/07-api-recipes.md`. Keyless. Batch 15 per 10s.
- **Semantic Scholar** needs a key in practice; keyless 429s by roughly the third call.
- **OpenAlex** free-versus-metered is unresolved (`open-questions.md`). Handle a 402 or a
  credit-exhaustion response as a normal degradation, not a crash.
- **TinyFish** is the news default, Exa news is the fallback.
- **GDELT** is keyless and returns a lot; cap and sort by date.

**Acceptance:** each source returns hits for a plausible query, each test is respx-mocked, and
`uv run pytest` passes with no network. A deliberately failing source returns `[]` and does not
raise.

**Verify:** `uv run pytest tests/sources/ -v`

---

## Phase 5: Normalize, dedupe, rank, resolve

**Deliverable:** the resolution layer.

**Files:**
- `core/resolve.py`
- `tests/test_resolve.py`

**How:** spec section 8. The two-source rule (D15) is the part that needs real test fixtures: a set
of same-name different-people cases that must NOT merge. Port the shape of `normalizeJob` and
`deduplicateJobs` from
`Discord-Job-Crawl-Server/utils/helpers.js`, including the
`normalizedId` idea for cross-source dedupe.

**Acceptance:** two hits for the same GitHub login from different sources merge into one entity.
Two different people with the same name do not merge. Confidence is a weighted sum, not a threshold
on one signal.

**Verify:** `uv run pytest tests/test_resolve.py -v`

---

## Phase 6: The dossier builder

**Deliverable:** `build_dossier(entity) -> Dossier`, with the drop-uncited rule.

**Files:**
- `core/dossier.py`
- `tests/test_dossier.py`

**How:** map entity hits to claims by field. Where a field has competing values (two employers),
keep both with their sources rather than picking. Drop any field with no `(value, source_url)` pair.
Record every source that returned nothing in `unavailable`, which becomes the output footer.

**Acceptance:** a dossier for a known person has claims from at least two sources. With Exa's key
removed, the dossier still builds and `unavailable` contains `exa`. No claim exists without a URL.

**Verify:** `uv run pytest tests/test_dossier.py -v`

---

## Phase 7: The discovery planner

**Deliverable:** `discover(description) -> list[Entity]`, the breadth planner.

**Files:**
- `core/discovery.py`
- `tests/test_discovery.py`

**How:** spec section 4.2. Same sources, different query construction: Exa `category:"people"` with
the description and no name, plus GitHub user/org search, news, and GDELT. Rank by evidence strength
and return each entity with the evidence that put it there.

**Acceptance:** a description query returns ranked entities, each carrying its evidence, and no
entity appears without at least one hit backing it.

**Verify:** `uv run pytest tests/test_discovery.py -v`

---

## Phase 8: The `people-core` MCP server

**Deliverable:** the core MCP surface: `discover`, `dossier`, `find_handle`, `list_sources`.

**Files:**
- `mcp/people_core.py`

**How:** FastMCP 3.x. `list_sources` reports each source's name, what it returns, whether a key is
required, and whether that key is present right now, so a model can explain a missing field instead
of guessing.

Register it. Note the two quirks that cost time on the prior Windows build: **servers load at
session startup**, so a new registration needs a restart, and **Windows paths in
`claude mcp add-json` must use forward slashes**.

```bash
claude mcp add-json people-core -s user \
  '{"type":"stdio","command":"uv","args":["run","--directory","/path/to/people-finder","python","mcp/people_core.py"]}'
```

**Acceptance:** `claude mcp list` shows `people-core` connected after a restart, and a natural-language
dossier request in a session returns a cited result.

**Verify:** `claude mcp list` and one live query in a session.

---

## Phase 9: The instrument layer

**Deliverable:** LinkedIn, Instagram, X, Reddit, and transcripts in `instrument/`, plus the
`people-instrument` server.

**Files:**
- `instrument/linkedin.py`
- `instrument/instagram.py`
- `instrument/x.py`
- `instrument/reddit.py`
- `instrument/transcripts.py`
- `mcp/people_instrument.py`

**Order within the phase:** X and Reddit first, because they are treg calls needing no browser and
therefore prove the instrument boundary cheaply. LinkedIn second, via
`stickerdaniel/linkedin-mcp-server` (D17). Instagram and transcripts last.

**How:** every treg call pins the provider (`X-Treg-Route-Prefer` or `X-Treg-Route-Waterfall: 0`),
because routed misses are billed at the default $1/call ceiling. Run the boundary test again.

**Acceptance:** `uv run pytest` still passes with `instrument/` deleted. No `core/` module imports
anything from `instrument/`. A failing instrument call does not fail a core query.

**Verify:** `rm -rf instrument && uv run pytest` (restore after), then
`uv run pytest tests/test_boundary.py -v`

---

## Phase 10: The product-path schemas

**Deliverable:** `schemas/person.schema.json` and a consent schema, for the later product.

**Files:**
- `schemas/person.schema.json`
- `schemas/consent.schema.json`

**How:** the consented-directory record from spec section 17: display name or alias (member's
choice), verified current employer, team or function, broad seniority band, city, languages, topics
willing to help with, the handles the member chooses to publish, a last-confirmed date, and a
rolling response indicator. An append-only consent log with one entry per purpose. Nothing else.

**Acceptance:** the schema has no field for a phone number, home address, or inferred sensitive
trait. This is a design constraint being enforced by the schema, not a schema that happens to lack
them.

**Verify:** read the schema and confirm the three absences are deliberate.

---

## What is deliberately not on this roadmap

- **A UI.** The tool is an MCP server first because that is where the work happens. A UI is a product concern.
- **Any Facebook or WhatsApp source.** D12: no route exists.
- **Mongo, Redis, or any server-backed store.** D14 and D4.
- **Scheduled or background runs.** The tool answers a question when asked. Nothing polls. The proposed Follow phase keeps this: "what's new since" is computed on request, and the caller schedules it.
- **Any source not in spec section 7.** Adding one means adding an entry to `research/03-source-evaluation.md` first.

## Proposed next phases (not yet approved)

Phases 11 to 14 revive the 2021 Alias concept in a consent-first, API-only form: Follow ("what's new
since"), footprint-page rendering, claimed pages in the product, and an opt-in "ask my work" chat.
Details, acceptance criteria and gates are in
[`research/08-alias-revival-2026-10.md`](research/08-alias-revival-2026-10.md).

**Status 2026-10-17:** Phase 11 (Follow) and Phase 12 (footprint page) are implemented under D21 and
D22. Phases 13 and 14 remain proposals.
