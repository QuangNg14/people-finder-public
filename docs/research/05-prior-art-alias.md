# Prior art: Alias (2021)

Alias was a seed-stage startup that aggregated a person's public content (essays, papers, podcasts,
tweets, YouTube) into profile pages, with a chat-over-content page and a podcast tool as the focus.
The author interned there in summer 2021.

This document records what Alias contributes to this project, what it does not, and what must be
left behind. The short version: **the application source is unrecoverable, and that turns out not to
matter much.**

---

## Status of the source

The application source is not available. What remains is the author's own blog post about the
internship, which quotes the relevant code, and a small podcast-deeplink prototype.

**Why that matters less than it sounds:** everything Alias contributed that is still useful is
either in the blog post (which quotes the code) or in the prototype directory (which is complete).
The lost part is a Next.js plus Hasura application whose architecture is described below and whose
ideas are already re-implemented better in this design.

---

## What Alias was

**Product.** "Aggregating content for influencers. The content can be essays, papers, podcasts,
tweets or youtube videos." A profile page per person, a bio edited by admins, cartoon avatars with a
Twitter avatar fallback, and a chat page over the aggregated content.

**Stack (2021):** Next.js plus TypeScript plus Tailwind on the front end; GraphQL via Hasura and
PostgreSQL on the back end, deployed to Heroku; Docker to containerise Hasura; Vercel for front-end
auto-deployment per commit; Notion as the task dashboard.

**The intern's five tasks, from the blog post:**
1. Added a `role` column with an enum foreign key, replacing a hardcoded admin email list in the code.
2. Fixed profile images: hand-made cartoon avatar if present, else the Twitter avatar already in the database.
3. Biography editing via EditorJS (HTML stored as a string) plus hyperlink support.
4. Page performance: image resizing, Next Image, dynamic imports for code-splitting, replacing the full FontAwesome import with Figma-generated SVGs, and static rendering of the homepage.
5. Podcast deeplinks: from a Listen Notes link, resolve the Spotify and Apple Podcast episode URLs.

---

## What survives

### 1. The concept, now with the right framing

Alias aggregated a person's public content into a profile. That is the same shape as the depth
(dossier) planner in this design: gather a person's public footprint and present it as one view.

The difference is decisive. Alias built **profile pages backed by a stored database**, which is the
Proxycurl-shaped model. This design builds **retrieval that cites and stores nothing** (D4). The
concept transfers; the architecture does not, and should not.

The other difference is that Alias started from a curated influencer list, while this starts from a
query. Discovery is the part Alias never had, and it is half of what this project is for.

### 2. Two working podcast API recipes

The most concrete thing that survives, and it lives in `07-api-recipes.md` so it is not lost again:

- **The undocumented iTunes episode search.** `https://itunes.apple.com/search?term=<title>&entity=podcastEpisode`, keyless, returns `trackViewUrl` for the Apple Podcasts episode. The blog post notes it "is not in the documentation and it took me a long time to figure it out."
- **Spotify episode search by title** via the client-credentials flow, then `GET /v1/search?q=<title>&type=episode&market=US` and read `episodes.items[0].external_urls.spotify`.

Only the iTunes one is adopted as a source, because it is keyless and Spotify's search was capped to
10 results in February 2026. The Spotify recipe is retained for reference.

### 3. The batch-and-sleep pattern

The prototype throttles in batches rather than per request: 50 items per 5-second delay for Spotify,
15 per 10-second delay for iTunes. Crude, but it is the right shape and the tunable constants are
worth keeping as a starting point for the per-source rate limiting in `core/http.py`.

### 4. A negative result worth recording

Alias's podcast pipeline went **Listen Notes for discovery, then per-platform search to resolve
deeplinks**. That two-step shape is directly reusable: discover episodes from a feed-level index,
then resolve canonical URLs per platform. The listen-notes layer is deferred (see
`03-source-evaluation.md`), but the iTunes resolution step is adopted.

---

## What must be left behind

- **Hasura plus Postgres.** The local Docker setup (`hasura/graphql-engine:v1.3.3`, Postgres 12) is 2021-vintage and has no place here. This design's persistence is one SQLite table (D4).
- **The `role` enum pattern.** A sensible fix for a 2021 problem that this project does not have.
- **EditorJS biography storage.** Storing HTML as a string in the database is the kind of decision that makes a later export or sanitisation pass painful. Not carried forward.

---

## The honest summary

Alias contributes **one concept** (a person's public footprint as a single view), **one adopted
recipe** (keyless iTunes episode search), **one pattern** (batch throttling), and **one warning**
(a stored people-and-content database is the model that got Proxycurl shut down). Everything else is
either unrecoverable or belongs to a stack that is four years and two architectural generations out
of date.

That is a thin harvest, and it is worth stating plainly rather than inflating it. The concept was
right and the execution model was the one this design exists to avoid.

---

## Update 2026-10-17

- **Identity confirmed:** Alias is alias.co, launched as "Show HN: Alias, Google Alerts for your favorite people" (2021-07-22). The headline feature was **alerts on new content from people you follow**, not only profile pages. The site is still live.
- **What to do with the concept now:** see [`08-alias-revival-2026-10.md`](08-alias-revival-2026-10.md), which proposes pull-based Follow, footprint-page rendering, and consented claimed pages, and records what must not come back.
