# Source evaluation

Every candidate source that was considered, with its cost, its access path, and the verdict. The
ones with a USE verdict are the source list in section 7 of the master spec; the rest are here so
that a future session does not re-evaluate them from scratch, or worse, adopt one.

Prices verified 2026-10-13 and 2026-10-14. Where a price moved recently it is noted, because several
of these changed inside a two-month window.

---

## Adopted: the core layer

| Source | Returns | Cost | Key | Why adopted |
|---|---|---|---|---|
| **Exa `category:"people"`** | structured person entity: name, location, `workHistory[]`, `educationHistory[]`, `research` with hIndex and notable works | $0.004/call, inside the $10/month resetting credit | `EXA_API_KEY` | The spine. The only evaluated source returning a *person entity* rather than a page or a link. Reads the public web, not a proprietary scraped database. |
| **TinyFish news** | news articles | **$0.00/call (verified)** | key | Default news route. Free. |
| **Exa `category:"news"`** | news articles | $0.007/call, same credit | same | News fallback when TinyFish is unavailable or a query needs semantic ranking. |
| **OpenAlex** | works, authors, institutions, hIndex, coauthors | free | free key recommended | Researchers. The lowest-risk category of source. |
| **GitHub Search** | users, org members, contributors | free, 10 req/min unauthed, 5,000 req/hr authed, 30/min search | `GITHUB_TOKEN` | Engineers and OSS contributors. The token is required in practice. |
| **YouTube Data API v3** | channels, uploads, video metadata | free, 10,000 units/day | `YOUTUBE_API_KEY` | Creators and anyone who speaks on video. |
| **Podcast Index** | podcast and episode metadata | free | key + secret | Podcast appearances. |
| **iTunes Search API** | episode lookup via `entity=podcastEpisode` | free, **no key** | none | Undocumented recipe recovered from the 2021 prototype. See `07-api-recipes.md`. |
| **GDELT 2.0** | global news mentions with tone and location | free, no key | none | Long-tail news. |
| **Semantic Scholar** | papers, authors, citation counts | free | **key required in practice** | Complements OpenAlex. Keyless throws 429 by roughly the third call. |
| **ORCID public API** | researcher identity, stable IDs | free | none | Strong identity signal for the merge rule (D15). |

---

## Adopted: the instrument layer

| Source | Route | Cost | Note |
|---|---|---|---|
| **LinkedIn** | `stickerdaniel/linkedin-mcp-server` (Apache-2.0) | free | `search_people` by keyword, location, connection degree, current company; `get_person_profile`; `get_company_employees`. Cookie import via `--import-from-browser` or `--login`. |
| **X** | treg, **provider pinned** | per call, roughly $0.005/read | Pin with `X-Treg-Route-Prefer` or `X-Treg-Route-Waterfall: 0`. |
| **Reddit** | treg, **provider pinned** | per call | Same pinning requirement. Non-commercial use only on the free tier. |
| **Instagram** | `instaloader` | free | Public professional profiles only. |
| **YouTube transcripts** | `yt-dlp` + `youtube-transcript-api` | free | Content, not just metadata. |

---

## Rejected, with the reason

These are the ones a future session is most likely to try to re-adopt, so each carries the specific
reason it was rejected.

| Candidate | Cost | Verdict | Reason |
|---|---|---|---|
| **Meta Muse / Meta Model API** | Muse Spark 1.3: $1.25/M in, $4.25/M out. `web_search` tool at $2.50/1,000 searches. Contributor tier: $0.10/M in, $0.20/M out. | **REJECT** | An LLM family, not a content index. No endpoint returns a person, profile, or social-graph data. `web_search` is generic with no people vertical, at a price Exa and TinyFish beat with structured output or free. Contributor tier is disqualified because Meta may train on prompts. Full detail below. |
| **Google Programmable Search** | 100 queries/day free | **REJECT** | Closed to new customers, discontinued 2027-01-01. |
| **Apify** | LinkedIn people-search actors $4 to $25 per 1,000 profiles; platform floors $29/$199/$999; residential proxy ~$7 to $8 per GB | **REJECT for core** | Infrastructure only, zero risk transfer (see `02-legal-boundaries.md`). Pricing moved to pay-per-event 2026-10-01. Instrument use only. |
| **treg.to** | per successful call, 0% markup, $1 free credit; LinkedIn from ~$0.00045/success; email find/verify ~$0.009; enrichment ~$0.028 | **REJECT for LinkedIn/Meta** | Inherits the scraper's legal risk, no published retention policy, no single controller for deletion. **Also: routed misses are billed**, default `X-Treg-Route-Max-Cost` $1/call, so unpinned routes charge for failures. Instrument use only, pinned. |
| **Apollo.io** | free tier, then $49 to $119/seat/month | **REJECT** | B2B contact database with mixed sourcing. Forbidden by D4. |
| **RocketReach** | $53+/month | **REJECT** | Same. |
| **People Data Labs** | volume/custom | **REJECT** | Identity-resolution dataset. Company-level use only; overkill and forbidden by D4. |
| **Clay** | $185 to $495/month | **REJECT** | Orchestrates 50+ providers, so it inherits every provider's risk, at a price with no personal-use case. |
| **Crustdata** | roughly $500+/month | **REJECT** | Hiring and headcount signals. Not cost-effective and not a person-retrieval source. |
| **Proxycurl** | defunct | **REJECT** | Sued, then shut down July 2025, data deleted. The cautionary tale that produced D4. |
| **LinkedIn SNAP** | enterprise | **REJECT** | Closed to new partners. |
| **SerpApi** | roughly $50+/month | **REJECT** | Wraps Google results, ToS-grey. Exa and TinyFish cover it better and cheaper. |
| **Bing Search API** | retired | **REJECT** | Retired 2025-08-11. |
| **Hunter.io** | free 50/month, then ~€34/month | **DEFER** | Legitimate for verifying one already-chosen person's work email. Not a discovery source. Belongs to a later outreach phase that is out of scope. |
| **NewsAPI** | dev free, commercial paid | **REJECT** | TinyFish and GDELT are free and cover it. |
| **Spotify Web API** | free, client credentials | **PARTIAL** | February 2026: search capped at 10 results, user endpoints removed except `/me`. Usable with a caveat; the keyless iTunes route is better for episodes. |
| **Listen Notes** | free tier ~150 to 300 req/month, 30 results/query | **DEFER** | Full-text episode search is better than Podcast Index's feed-level search, but the free tier is thin and branding is required. Revisit if podcast coverage proves insufficient. |

---

## Meta Muse in detail

Verified against live Meta documentation on 2026-10-14, not against prior notes (which have been
stale twice).

**What it is.** A model family on the Meta Model API at `https://api.meta.ai/v1`, bearer token auth,
drop-in compatible with the OpenAI SDK, the Anthropic SDK, and OpenAI-compatible agent CLIs.

| Model | Notes |
|---|---|
| `muse-wonder-1.0` | Most capable, long-horizon agentic work, 1,048,576-token context, in preview |
| `muse-spark-1.3` / `1.2` / `1.1` | Reasoning always on, 1M-token context, max output ~131,072 tokens. Default is 1.1 if unspecified |
| `muse-spark-*-contributor` | Discounted, with a training-data clause |
| `muse-image-1.0` | Generation and editing |
| `muse-voice-transcribe-1.0` | Speech to text, $0.18/hour |
| `sam-3.1` | Text-prompted segmentation |
| `muse-glimmer` | Open-weight, self-hosted via vLLM / SGLang / llama.cpp / ExecuTorch. Not called through the API |

`muse-code` is **not a model**. It is a terminal and CI coding agent from Meta.

**Rate limits** are per team, not per key: 3,000 RPM / 4M TPM on Standard, 100 RPM / 3M TPM on
Contributor.

**What it can retrieve.** Muse Spark accepts a `web_search` tool with inline citations, billed at
$2.50 per 1,000 searches, reported via `usage.tool_usage`. Grounding is available mainly through the
Responses API endpoint.

**What it cannot do.** No endpoint, model, or tool returns a person, a profile, or social-graph data.
Muse's consumer agent connects only to the user's own apps, per-service, with no path to other
users' Facebook, Instagram, or Threads data.

| Candidate role | Verdict | Reason |
|---|---|---|
| Retrieval source | REJECT | `web_search` at roughly $0.0025/query with no people vertical and no structured entity. Exa returns a structured person at $0.004 and is free under the credit; TinyFish news is $0.00. Strictly worse per unit of person signal. |
| Synthesis brain | REJECT as default | $4.25/M output to do what the calling agent does at zero marginal cost. |
| Contributor tier | DISQUALIFIED | Meta may train on prompts and completions, conflicting with the standing rule against uploading contact information to external AI services. |

**Pricing caveat:** Meta's docs state $2.50 per 1,000 searches while a third-party tracker reports
$0.00825/query. These differ by roughly 3x and do not reconcile. Re-check at
`dev.meta.ai/docs/pricing-rate-limits` before any budget depends on it. This does not affect the
decision, which rests on capability, not price.

**Note on the repeated confusion:** the premise "Meta Muse APIs for people search" conflates two
different products. The Meta Model API is an LLM inference endpoint and is usable only as a
summarizer or drafter, never as a data source. Muse the consumer agent is a separate product
(US only, $20 or $100 per month, no developer people API).

---

## OpenAlex: keyless confirmed working

Official documentation states OpenAlex data is free, including casual API use. A third-party source
claims OpenAlex became key-required and credit-metered in February 2026. The reported pricing page
404s.

**Live check, 2026-10-14:** a keyless `GET /authors?search=...` returned 200 with full author
records (`summary_stats.h_index`, `last_known_institutions`, `topics`). The keyed call has not been
made yet. The source sends `mailto` when `OPENALEX_EMAIL` is set and treats a 402 or any
credit-exhaustion response as a normal degradation (`tests/sources/test_core_sources.py`).

---

## Cost summary

| Layer | Monthly cost |
|---|---|
| Exa (spine plus news fallback) | **$0.00** up to ~2,500 people searches, inside the $10/month credit |
| TinyFish, OpenAlex, GitHub, YouTube, Podcast Index, iTunes, GDELT, Semantic Scholar, ORCID | $0.00 |
| SQLite, Python, uv, FastMCP | $0.00 |
| **Core total** | **$0.00/month** |
| Instrument (X, Reddit via treg) | per call, only when used |
| Instrument (LinkedIn, Instagram, transcripts) | $0.00 |

The core is free. That is a deliberate outcome of source selection, not a coincidence: the
product-safe half has no ongoing cost, so the personal tool runs indefinitely and a shipped product
has no per-user infrastructure cost.
