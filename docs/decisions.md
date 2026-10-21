# Decisions

Append-only. Each entry states the decision, the evidence behind it, and the alternatives that were
rejected. Read this before changing the design: most things that look like missing features are
decisions that were made deliberately, usually for a reason recorded here.

Dates are the date the decision was made. Decisions 1 to 13 were made on 2026-10-14 in the design
session; the earlier dated ones are carried forward from the prior research and are included because
they still bind.

---

## D1. Personal tool first, with a product-safe core

**2026-10-14.** Build for personal use, but make the two pieces a product would keep (cited
retrieval, consented directory schema) the centre of the design, so shipping later is an addition
rather than a rewrite.

**Because:** personal use and shipped product are two different legal objects. Personal retrieval
for one's own networking creates no stored database and has no users. A shipped product is a data
controller with deletion obligations. Building the product-safe core now means the fork costs
nothing later.

**Rejected:** build the product first (wrong risk order, and the product needs an audience that does
not exist yet); build a throwaway personal script (would be rewritten entirely on the first product
attempt).

---

## D2. Engine-first, both planners on one engine

**2026-10-14.** Build the shared retrieval engine (sources, normalizer, resolver, MCP surface) and
put both query planners on top: depth (dossier about one person) and breadth (discovery of people
matching a description).

**Because:** the two planners differ only in query construction and result shaping. Building either
one alone would duplicate the sources, the normalizer, and the cache.

**Rejected:** depth only (the more compelling demo, but it strands the discovery use case that
prompted the project); breadth only.

---

## D3. Two packages, `core/` and `instrument/`, separated by process and enforced by test

**2026-10-14.** Official-API retrieval and scraping live in different packages, run in different MCP
servers, and `core/` must pass its own tests with `instrument/` deleted. A boundary test asserts `core/`
never imports `instrument/`, and packaging excludes `instrument/` from the wheel.

**Because:** a comment saying "do not use scrapers here" survives exactly until the first time a
scraper is convenient. This is a mechanical guarantee, which is the only kind that holds.

**Rejected:** one package with a `sources/scrapers/` subdirectory and a naming convention (decays);
a config flag (a flag is one merge away from being wrong).

---

## D4. No person database. A TTL cache of raw provider responses is the only persistence.

**2026-10-14.** Person-shaped data exists in memory for the duration of a query and is never
written. The only table is `http_cache`.

**Because:** the stored-scraped-people-database is the Proxycurl path, and it ends in a lawsuit
regardless of data quality. A cache of raw responses with a TTL is not a database of people, and it
is also the quota-protection mechanism.

**Rejected:** a Mongo or SQLite person table for "just caching" (it becomes the product's data
model by default); no cache at all (burns quota on repeat queries and has no 429 fallback).

**Amended 2026-10-17 (see D22):** one narrow exception. A caller-requested local export of a single
rendering (`python -m core page ... --out <path>`) may be written. The engine never tracks, indexes,
updates or re-reads such files; they are the caller's documents. Without `--out`, nothing
person-shaped is written.

---

## D5. `Claim.source_url` is required and has no default

**2026-10-14.** The citation invariant is enforced by the type system. There is no way to construct
a claim without a source URL. The assembler additionally drops any field for which no
`(value, source_url)` pair exists, rather than emitting a guess.

**Because:** it makes uncited output unconstructable rather than a bug to catch in review. The same
approach is what gave the prior finder its "no stored phone number" property.

**Rejected:** an optional source URL with a lint rule (lint is advisory); a post-hoc validator
(catches it late, and the assembler is where guesses would be introduced).

---

## D6. Exa `category:"people"` is the spine source

**2026-10-14.** Exa's people vertical is the primary retrieval source for both planners.

**Because:** it is the only evaluated source that returns a structured *person entity* (name,
location, `workHistory[]`, `educationHistory[]`, `research` with hIndex and notable works) rather
than a page or a link. It reads the public web rather than a proprietary scraped database, so the
sourcing is materially cleaner than a LinkedIn reseller. It costs $0.004/call and sits inside the
$10/month resetting credit, so at personal volume it is free.

**Rejected:** Apollo, PDL, RocketReach (stored people databases, and D4 forbids the model);
LinkedIn resellers (see D11); Google Programmable Search (see D8).

---

## D7. TinyFish is the default news route, not Exa news

**2026-10-14.** News retrieval defaults to TinyFish at $0.00/call, with Exa `category:"news"` at
$0.007/call as the fallback.

**Because:** free is free. Where two sources return the same thing, the cheaper one is the default
and the other is the fallback.

**Rejected:** Exa news as default (it becomes the fallback, so it is still implemented, just not
first).

---

## D8. Google Programmable Search is dropped

**2026-10-14.** The `pse` source from the prior Windows build is not carried forward. The vault
playbook's step 1, which depends on it, is now wrong.

**Because:** Google Programmable Search is closed to new customers and is discontinued
2027-01-01. Exa's people vertical covers the same discovery need with structured output and better
sourcing.

**Rejected:** keeping `pse` as a legacy path (a dead API is not a fallback, it is a failure that
looks like a feature).

---

## D9. Meta Muse and the Meta Model API are rejected

**2026-10-14.** Verified against live Meta documentation, not against prior notes.

**Because:** Muse is a model family, not a content index. It cannot search for people. Its
`web_search` grounding is a generic web retrieval tool at roughly $0.0025/query with no people
vertical and no structured person entity, which is strictly worse per unit of person signal than Exa
(free, structured, people-specific) or TinyFish (free, news). As a synthesis brain, Muse Spark 1.3
costs $1.25/M input and $4.25/M output to do work the calling agent already does at zero marginal
cost. The Contributor tier is disqualified outright because Meta may train on prompts and
completions, which conflicts directly with the standing rule against uploading contact information
to external AI services.

**Rejected:** Muse as a retrieval source; Muse as a synthesizer; Muse Contributor tier.

**Caveat for anyone revisiting:** Meta's docs state $2.50 per 1,000 searches while a third-party
tracker reports $0.00825/query; these do not reconcile. Also, Muse Code is a terminal agent, not a
callable model. Full detail in `research/03-source-evaluation.md` and section 11 of the master spec.

---

## D10. Apify is an instrument, never a read path

**2026-10-13.** Apify actors may be used by the operator for research. They are never called by
`core/`.

**Because:** Apify's General Terms and Conditions supply infrastructure only, disclaim liability for
how the service is used, cap liability at 12 months of fees or $1,000, and make a user who breaches
a third-party right "fully liable." Buying a call through Apify moves the work, not the exposure.
The stated-ToS review, the GDPR and Decree 13 analysis, and the LinkedIn contract question all stay
with the user.

**Rejected:** Apify as a core source. Note also that Apify pricing moved to pay-per-event on
2026-10-01 and LinkedIn people-search actors run $4 to $25 per 1,000 profiles, with residential
proxy bandwidth billed separately at roughly $7 to $8 per GB.

---

## D11. treg is an instrument, and every treg call must pin the provider

**2026-10-14.** treg is not a data owner. Its LinkedIn and Instagram/Facebook endpoints route
through scraping vendors (Bright Data, Apify, HarvestAPI, ContactOut, Enrichlayer, ScrapeCreators)
and it inherits their legal risk. Where it is used at all, in the instrument layer for X and Reddit,
the provider is pinned explicitly.

**Because:** routing is per call, so one key can silently land on a vendor with a weaker consent
posture, and there is no published retention policy and no single controller to serve a deletion
request. Separately, **routed misses are billed too**: the default `X-Treg-Route-Max-Cost` is
$1/call, so an unpinned route charges for failures.

**Rejected:** treg for LinkedIn or Meta person lookups (the 114 LinkedIn endpoints route mostly
through scrapers, and the last vendor that did this at scale was sued and shut down).

---

## D12. Facebook and WhatsApp have no route. The consented directory is the only path.

**2026-10-14.** No Facebook source is implemented. No WhatsApp source exists. Instagram handles are
obtainable only for professional accounts and only in the instrument layer.

**Because:** the Graph API has no arbitrary-person content search; it is for pages you manage. No
public API returns Facebook or WhatsApp handles, and no scraper does so reliably. The one fact that
frames the entire project: **Facebook, WhatsApp, and Instagram handles only ever come from the
person.** That makes the consented directory, where the person supplies their own detail, not a
compliance compromise but the only route to a complete record.

**Rejected:** logged-in automation (prohibited under Meta v. Bright Data reasoning about logged-in
ToS, and blocked technically); logged-out scraping of public data (not a contract breach per that
case, but Meta blocks it, and the fetch patterns are hostile to maintain).

---

## D13. Stack: Python 3.13, uv, pydantic v2, httpx, FastMCP, ruff, mypy, pytest, respx, SQLite

**2026-10-14.** As listed in section 12 of the master spec.

**Because:** chosen for cost and currency, per the direction that the 2021 Alias stack is too old to
copy. FastMCP 3.x is the most-adopted Python MCP framework, so the protocol layer is not
hand-rolled. respx mocks httpx at the transport layer, so every source is testable without network.

**Retracted:** the prior build's "stdlib only, no dependencies, Python 3.10+" recommendation. It
bought a zero-install story at the cost of hand-rolled JSON-RPC, hand-rolled HTTP retries, and no
type checking on the one invariant that matters. That trade does not survive contact with a real
codebase.

**Rejected:** staying on the stdlib; Node/TypeScript (the V1 engine belongs in Python because the
surviving prior art and the user's other tooling are Python, and the instrument layer arrives mostly
as prebuilt MCP servers).

---

## D14. Port the job crawler's patterns, not its code. No MongoDB.

**2026-10-14.** The source registry, the normalize/dedupe/rank layer, and the Docker image pattern
come from `Discord-Job-Crawl-Server/`. The code does not.

**Because:** the crawler's Mongo service is 14 exported functions doing what one SQLite table does
here, and D4 forbids a person collection anyway. Running a database server for a cache is
infrastructure without a reason. The patterns that survive translation are the module contract
(`availableScrapers` becomes `SOURCES`), the normalize-then-dedupe pipeline, and the MODE-driven
container.

**Rejected:** porting the crawler wholesale; adopting Mongo; adopting puppeteer-extra and the
stealth plugin in the core (they belong to the instrument layer, if anywhere).

---

## D15. A merge into one Entity requires corroboration from two independent sources

**2026-10-14.** Name alone never merges two people.

**Because:** name collision is the dominant failure mode in people search, and a false merge is far
worse than a duplicate. A false merge puts one person's publication next to another person's
employer and cites both, which is exactly the failure that makes an output untrustworthy. Matching
signals ranked strongest first: ORCID, GitHub login, a shared personal domain, exact email
local-part match, name plus a corroborating org, name alone.

**Rejected:** fuzzy name matching with a similarity threshold (the standard approach, and the one
that produces confidently wrong merges).

---

## D16. The repository lives outside the Obsidian vault

**2026-10-14.** At `people-finder/`.

**Because:** keys must never be in the vault, and code inside a vault invites note-sync, backup, and
search tooling to touch it. The prior build's open question was whether the finder should move under
vault tooling; the answer is no.

---

## D17. LinkedIn in the instrument layer uses `stickerdaniel/linkedin-mcp-server`

**2026-10-14.** Chosen over the alternatives surveyed in `research/04-github-landscape.md`.

**Because:** it is Apache-2.0, maintained, and exposes the operations that matter
(`search_people` by keyword, location, connection degree, and current company; `get_person_profile`;
`get_company_employees`), with cookie import via `--import-from-browser` or `--login`. The
alternative LinkedIn tools are stale (last pushed 2022 to 2024), unlicensed, or a direct repeat of
the Proxycurl mistake.

**Note:** it is a scraper regardless of any "official API" framing, which is precisely why it lives
in `instrument/` and why D3 exists.

---

## D18. Source degradation is per-source isolation, and unavailable sources are named

**2026-10-14.** A failing source returns `[]` and never propagates. A missing key reports
`unavailable` in `list_sources` and appears in the output footer.

**Because:** silent absence is the failure mode that makes a thin dossier look like a complete one.
The worst outcome is not a failed lookup, it is a user believing a two-field dossier is the whole
record.

**Rejected:** fail-fast on any source error (one flaky free API would take down every query); silent
skipping (indistinguishable from "no results found").

---

## D19. Shortlists expire 90 days after the outreach cycle unless the person replied

**2026-10-13.** Carried forward from the prior build's encoded boundaries.

**Because:** it bounds retention without requiring a policy document, and it matches the workflow
the tool exists to serve (an outreach campaign has a natural end).

---

## D20. Discovery only. Never auto-connect, never auto-send.

**2026-10-12.** Carried forward and not revisited.

**Because:** auto-connect and auto-DM on LinkedIn is both the behaviour that gets accounts banned
and the exact behaviour LinkedIn litigates. The tool finds people and evidence about them; a human
decides what to do with that.

**Rejected:** auto-connect or auto-DM with a rate limit (a rate limit is not a defence, and the
behaviour is the harm).

---

## D21. Follow is pull-based over a user-owned watchlist

**2026-10-17.** `whats_new` (CLI `whats-new`, MCP `whats_new`) computes "what's new since a date" on
request, for people given inline or in a TOML watchlist the caller owns. Results split into
`published` (a provider publication date on or after `since`) and `newly_observed` (only an
observation date, such as GDELT `seendate`, or no usable date).

**Because:** "Google Alerts for your favorite people" was the 2021 Alias pitch and the most useful
part of it, but polling and stored profiles would break the roadmap's no-background-runs rule and
D4. Mixing observation dates with publication dates would report old items as new.

**Rejected:** a scheduler inside the engine (the caller schedules); storing a watchlist or "last
seen" cursor in the cache (person-shaped state); treating GDELT dates as publication dates.

---

## D22. Pages are renderings, not records

**2026-10-17.** The footprint page (`page` / `footprint_page`) renders a `Dossier` as Markdown and
returns it. Content in the dossier now includes works, repos and uploads fetched by the resolved
person's own identifiers (OpenAlex author, Semantic Scholar author, GitHub login, YouTube channel),
which are marked `match="identifier"` and carry full confidence.

**Because:** Alias's profile page was the right view and the wrong storage model. A rendering keeps
the view and stays inside D4, with the narrow export amendment recorded there.

**Rejected:** persisting pages (the product path stores only claimed, consented pages, outside this
engine); fetching content by name (a same-name stranger's papers would be attached).

Proposed but not decided: D23, an opt-in "ask my work" chat for claimed pages only
(`research/08-alias-revival-2026-10.md`).
