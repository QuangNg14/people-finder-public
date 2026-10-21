# Alias revival: should the 2021 concept continue, and in what form

Date: 2026-10-17. Status: Phases 11 (Follow) and 12 (footprint page) implemented (decisions D21,
D22 and the D4 export amendment); Phases 13-14 still proposals. Builds on
[`05-prior-art-alias.md`](05-prior-art-alias.md), [`02-legal-boundaries.md`](02-legal-boundaries.md)
and the master design. Web claims come from a research pass on 2026-10-17; anything marked
UNVERIFIED was not confirmed against a primary source.

As of 2026-10-17, alias.co is an alert service for about 63 founders, with no search, and its
person content pages return 404.

---

## Verdict

**Yes, continue the concept; no, do not resume or rebuild Alias as it was.**

- **The codebase cannot be resumed.** The application source is not available.
- **The idea has been validated by others.** A person's public work in one place, plus "ask their work," is now a funded category: Delphi raised a $16M Series A in 2025.
- **The 2021 execution model is now a liability.** That model meant profiling anyone, using Spotify and X data, with no consent. Platform terms ban AI ingestion, US state right-of-publicity laws now cover AI personas, and the EU AI Act requires disclosure. The generic "profile page" category has also collapsed (Bento, Read.cv, Polywork and Google People Cards are all gone).

The revival that fits people-finder's design, and Pathwise's distribution, has three layers, in this order:

1. **Follow (personal, now).** "Google Alerts for your favorite people," which was Alias's actual launch pitch, rebuilt as a pull-based, cited "what's new" over official APIs.
2. **Footprint page (personal, now).** Alias's profile page, rendered from a dossier: essays, papers, podcasts, videos and repos, each cited, with nothing stored.
3. **Claimed pages (product, later).** The consented directory from spec section 17. The person verifies and curates their own page; Pathwise mentors and advisors come first. An opt-in "ask my work" chat comes only after that, and only for claimed pages.

---

## 1. What Alias actually was (identity now confirmed)

Previously the docs knew Alias only from the intern blog post. The 2026-10-17 research identified it:

- **alias.co.** Archived JSON shows per-person `essayCount`, `podcastCount`, `tweetCount`, `videoCount`, routes like `/[slug]/essays` and `/[slug]/podcasts`, a separate `cartoon_uuid`, an `/admin` route, and Hasura `__typename: "influencers"` payloads.
- **Launch:** "Show HN: Alias, Google Alerts for your favorite people" (2021-07-22, 153 points, news.ycombinator.com/item?id=27921875), after an earlier Show HN on 2021-06-10.
- **Podcast data** came from Listen Notes (episode images served from `cdn-images-1.listennotes.com`).
- **Status:** alias.co is still live as a "growing directory of influencers," served from Vercel. No shutdown or acquisition was found. Funding and current team are UNVERIFIED.
- The "chat over a person's content" feature in the intern recollection was **not** found in archives (UNVERIFIED).

**What this changes.** Alias's headline value was **alerts** (follow people, get their new content), not only static pages. people-finder has no equivalent today, and it is the cheapest piece to add.

## 2. The category since 2021

| Area | State in 2026 | Lesson |
|---|---|---|
| Chat with a person's knowledge | **Delphi** (delphi.co): Free, Builder $79/mo, Scaler $299/mo; $16M Series A (Sequoia, 2025); creators such as Jay Shetty. Started with unconsented demos (Steve Jobs, Buffett), now requires users to clone only themselves or with permission, plus ID verification | The idea works when the person opts in and pays. Consent became mandatory, not optional |
| Universal profile pages | Linktree dominant. **Bento shut down** (Feb 2026, folded into Linktree). **Read.cv** acquired by Perplexity and closed (2025). **Polywork shut down** (Jan 2025). **Google People Cards** discontinued (2024). Peerlist and Contra are alive with a niche focus | Thin aggregation is not a business. Pages need a job to do, such as hiring, mentoring, booking or credibility |
| Podcast guest intelligence | Podchaser (owned by Acast since 2022; pricing gated), Listen Notes (Pro $200/mo; no person entity), Rephonic ($99-299/mo), Podcast Index `podcast:person` tag (free, adoption unknown) | Guest-appearance data is valuable and partly free. iTunes plus Podcast Index already cover the free tier |
| Academic profiles | ORCID, OpenAlex, Semantic Scholar remain free and open | The most durable official-API layer, already in core |

## 3. What changed legally and on platforms (relevant to any revival)

- **Spotify Developer Policy (effective 2025-05-15):**
  - bans ingesting Spotify content into ML or AI models (III.14);
  - bars apps with a specific artist as the sole subject without permission (III.1);
  - extended quota needs a registered business with 250k MAU.
  - **Spotify stays reference-only** (already D7); never use it for a single-person page or chat.
- **X:** API terms ban using content to train or fine-tune models (June 2025). No X in core (already D12/instrument-only).
- **YouTube:** the Data API limits retention and derivative use. `youtube-transcript-api` uses unofficial endpoints. Transcripts stay in `instrument/`, never in a product read path.
- **Right of publicity and AI personas:**
  - Tennessee ELVIS Act (2024; voice protected, reaches tool makers);
  - New York Civil Rights Law 50-f (digital replicas);
  - California AB 1836 and AB 2602 (2025);
  - Carlin estate v. Dudesy (settled 2024; copyright plus publicity for an AI imitation).
  - The federal NO FAKES Act is pending.
  - Conclusion: **no "speak as person X" chat without that person's written permission.**
- **EU AI Act Article 50:** applicable from 2026-08-02. A chatbot must disclose that it is AI; synthetic content must be marked.
- **Vietnam:** Decree 13/2023 was superseded by the **Personal Data Protection Law No. 91/2025/QH15, effective 2026-01-01** (VERIFY implementing details). It is consent-centric and extraterritorial, with no clear journalism-style exemption. The consented-directory design already assumes consent; the `02` text that names Decree 13 now carries an update note.
- **Copyright:** linking is safe. Hosting full text or RAG over others' articles is contested (Dow Jones v. Perplexity, ongoing). Keep "ask my work" to content the person owns and uploads or authorizes.

## 4. Options evaluated

| Option | Verdict | Why |
|---|---|---|
| Resume the Alias codebase | **No** | Main source not recovered (re-checked after the copy finished); the 2021 stack (Hasura v1.3, Heroku) is obsolete either way |
| Rebuild Alias as a public influencer directory with stored profiles | **No** | Proxycurl-shaped liability (D4); the category is in decline; Spotify single-subject rule |
| **Follow: pull-based "what's new"** over official APIs | **Yes, Phase 11** | Alias's actual pitch; cheap (cursor by date over existing sources); useful personally and for Pathwise advisor alerts |
| **Footprint page**: render a dossier as Alias-style tabs | **Yes, Phase 12** | Reuses the dossier; no storage; cited by construction |
| **Claimed pages** (consented directory) for Pathwise mentors and advisors | **Yes, Phase 13, product path** | Consent is trivial (they are Pathwise users); gives mentors credibility; matches spec section 17 |
| Opt-in "ask my work" chat | **Later, Phase 14, gated** | Delphi is the funded incumbent; only worth it for a niche (Vietnamese mentors, academics) after Phase 13 proves demand |
| Appearance tracker for academics and professionals | **Fold into Phases 11-12** | Podcast Index plus iTunes plus YouTube already give it; sell later as a Pathwise feature, not a product |
| Speaker one-pager for event organizers | **Park** | Sales-heavy niche; a byproduct of Phase 12 if ever needed |
| Voice or avatar clones | **Never** | ELVIS Act and NY 50-f exposure; outside the product's purpose |

## 5. Proposed phases (amendment to `roadmap.md`)

Same format and gate as the roadmap: `uv run ruff check . && uv run mypy && uv run pytest` passes at the end of every phase.

### Phase 11: Follow ("what's new since")

**Deliverable:** `core/follow.py`, a `whats_new` MCP tool in `people-core`, and `python -m core whats-new`.

**How:**
- Input: one or more people, or a watchlist **file the user owns** (YAML of identifiers: OpenAlex ID, ORCID, GitHub login, YouTube channel ID, podcast person name), plus a `since` date.
- Each source gets a `since`-aware call:
  - OpenAlex works filtered by author and `from_publication_date`;
  - Semantic Scholar author papers;
  - GitHub public repos and releases;
  - YouTube Data API search by `channelId` and `publishedAfter`;
  - Podcast Index `byperson` filtered by date;
  - GDELT and TinyFish with a date window.
- Output: new items only, each cited, newest first, with the footer naming silent sources.
- **Two date semantics, never mixed.**
  - `published` items have a provider publication date on or after `since`: OpenAlex `publication_date`, YouTube `publishedAt`, Podcast Index `datePublished`, GitHub release `published_at`.
  - `newly_observed` items have only an observation time. GDELT exposes `seendate`, which is when GDELT saw an article, not when it was published. These go in a separately labeled list, never in the published list.
  - Items with no usable date go to `newly_observed`, never `published`.
- **Pull-based on purpose.** The roadmap excludes background polling. A user who wants a weekly digest schedules the command themselves; the engine still stores nothing but the cache (D4).

**Acceptance:**
- given 3 identities and a `since` date, the `published` list contains only items whose provider publication date is on or after `since`;
- a delayed-indexing GDELT fixture (published before `since`, seen after) lands in `newly_observed`, and an unknown-date fixture never appears in `published`;
- every item has a URL; same-name people are not merged; running it twice in a row hits the cache.

### Phase 12: Footprint page

**Deliverable:** two parts.
1. **Content retrieval in the dossier path.** Today the depth path retrieves *profiles*: OpenAlex and Semantic Scholar author records, and GitHub user profiles. Phase 11's content endpoints (OpenAlex works by author, Semantic Scholar author papers, GitHub public repos, YouTube channel uploads) are shared with the dossier assembler, so papers and code arrive as their own `Hit`s and `Claim`s, attached to the resolved identity.
2. **Rendering.** `core/page.py` renders the `Dossier` as Markdown (and optional static HTML), with Alias-style sections: papers, talks and podcasts, videos, writing and news, code. By default the rendering is **returned** (stdout for `python -m core page "Name"`, the MCP tool `footprint_page` returns text). `--out page.md` writes a file only when the caller explicitly asks (see the D4 amendment below).

**Acceptance:**
- fixtures where a known paper (OpenAlex work) and a known repository (GitHub) appear under the correct identity, each with its own item URL, not the profile URL;
- every rendered item links to its source;
- same-name alternates appear as a "not this person?" list, never merged;
- unavailable sources appear in the footer;
- without `--out`, nothing is written except the cache.

### Phase 13: Claimed pages (product path, implemented in Pathwise Prep, not here)

**Deliverable:** a design and schema extension for the consented directory, starting with Pathwise mentors and invited advisors.

**How:**
- The person proves control of identifiers: ORCID OAuth, GitHub OAuth, Google/YouTube OAuth for the channel, or a domain TXT record.
- The engine proposes items (Phase 12); the person approves, hides or reorders them.
- Only the approved list is stored, with source URLs and a consent log entry (`schemas/consent.schema.json` purpose `directory_listing`).
- Withdrawal revokes public visibility **immediately**. The stored page and approved items are then purged within a proposed **72-hour operational SLA**. That is an internal target, not a cited legal deadline: GDPR requires erasure "without undue delay" (Art. 17) with a one-month response window (Art. 12(3)), and the PDPL 91/2025/QH15 deadlines and implementing rules must be confirmed (VERIFY).
- `schemas/person.schema.json` gains an optional `published_items` array of `{kind, title, url, date}` with no free-text bodies.

**Acceptance:** a page cannot exist without a verified claim; deleting the claim deletes the page; nothing from `instrument/` can populate it.

### Phase 14: Opt-in "ask my work" (deferred, gated on Phase 13 demand)

**Scope:**
- Only for claimed pages.
- Retrieval only over content the person uploads or explicitly authorizes: their own essays, their own transcripts, and paper abstracts and metadata.
- Every answer cites items; the UI says "answers based on X's published work, generated by AI" (EU AI Act Art. 50).
- Never first-person impersonation, never voice.
- Rate-limited and logged for the owner.

**Gate:** start only if at least 20 claimed-page owners ask for it, and only after a counsel review of publicity and copyright terms in the owner agreement.

## 6. Where it plugs into Pathwise

| Pathwise surface | Alias-revival piece |
|---|---|
| Study-abroad Advisor Finder and Lab Fit Card (vault: `analyses/study-abroad-product-technical-design-2026-10.md`) | An **unclaimed footprint page** for a professor: retrieve-and-cite only, stores identifiers plus the student's notes |
| Advisor watchlist | **Follow**: "your saved professor published a new paper or got an NSF award" (pull-based digest in the study-abroad hub) |
| Mentors directory (`/mentors`) | **Claimed pages**: mentors verify GitHub, ORCID or YouTube, and curate their talks, papers and posts |
| Short-video content | "Google Alerts for your favorite people, legally" is itself a build-in-public story; the appearance tracker finds podcast guests to invite (opt-in outreach only) |

## 7. What must not come back

- A stored directory of people who did not opt in.
- Spotify as a data source for anything person-centric; X content in any model or retrieval path.
- Transcripts or full texts of other people's work stored or used for chat without the owner's authorization.
- Voice, avatar or first-person persona clones.
- Hardcoded credentials. Keys come from the environment only.

## 8. Decisions this would add (proposed, not yet in `decisions.md`)

- **D21. Follow is pull-based over a user-owned watchlist.** The engine computes "what's new since a date" on request; scheduling belongs to the caller; the only persistence is still the cache.
- **D22. Pages are renderings, not records.** The footprint page is a view of a `Dossier` returned to the caller; the engine never manages or re-reads stored pages, and product storage happens only after a verified claim.
- **D4 amendment (narrow), needed by D22.** "Person-shaped data is never written" gains one exception: a **caller-requested local export** (`--out <path>`) of a single rendering. The engine does not track, index, update or read such files. They are the caller's documents, like a saved search result. Without `--out`, the D4 invariant holds unchanged.
- **D23. "Ask my work" is consent-gated and non-impersonating.** Claimed pages only, owner-authorized content only, cited answers, AI disclosure, no voice.

## Sources (2026-10-17 research pass)

- Alias: news.ycombinator.com/item?id=27921875 and item?id=27463497; web.archive.org snapshots of alias.co (2021-2024).
- Delphi: delphi.co/pricing, delphi.co/about, delphi.co/blog/digital-identity-protection; finsmes.com (Series A, 2025-06-24).
- Category closures: Linktree/Bento notices; TechCrunch (Read.cv to Perplexity, 2025-01-17); Polywork DNS; Search Engine Roundtable (Google People Cards, 2024).
- Podcast: investors.acast.com (Podchaser); listennotes.com/api/pricing; rephonic.com pricing; podcastindex.org namespace.
- Platforms: developer.spotify.com policy (2025-05-15, III.1 and III.14); TechCrunch on X API terms (June 2025).
- Law: Tenn. Code 47-25-1105 (ELVIS Act); NY Civil Rights Law 50-f; gov.ca.gov (AB 1836, AB 2602); artificialintelligenceact.eu/article/50; DFDL on Vietnam PDPL 91/2025/QH15 (Jan 2026); Variety (Dow Jones v. Perplexity).
