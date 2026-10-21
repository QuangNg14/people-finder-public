# Platform reality: can you search a person's content?

Researched 2026-10-13, corrected 2026-10-14. This is the evidence behind the source selection in
section 7 of the master spec, and the answer to "why not just pull from X / Instagram / Facebook."

## The pattern

The platforms named first in the original request (X, Facebook, Instagram) are the hardest. The ones
named last (YouTube, podcasts, news) are the easiest. **The easy ones publish an index; the hard ones
deliberately do not.** That is not an accident of engineering effort, it is a strategic choice, and
it is why no amount of tooling effort closes the gap.

## The table

| Platform | Search a person's content? | Route | Cost and limits |
|---|---|---|---|
| **Threads** | Yes, officially | Graph API `/keyword_search` with an `author_username` filter, `search_type` TOP or RECENT, `since` and `until` | Needs the `threads_keyword_search` permission. Quota is small and reported inconsistently (roughly 500 per 7 days to 2,200 per day); verify in Meta's docs before relying on it. |
| **YouTube** | Yes | Data API v3: channel, uploads playlist, `search.list` | Free. `search.list` is near 100 calls/day on the free unit allocation; other endpoints share a 10,000 unit/day pool. |
| **Reddit** | Yes | OAuth API: `/user/<name>/submitted.json`, `/search.json` | Free tier is 100 QPM but **non-commercial only**, and app approval has been required since 2025. Commercial use is a manual enterprise contract. |
| **Instagram** | Professional accounts only | Graph API Business Discovery by handle, plus hashtag search | Business and Creator accounts only, never personal. Requires app review and business verification. Basic Display was retired December 2024. 30 unique hashtags per 7 days. |
| **Facebook** | **No** | The Graph API is for pages you manage | No arbitrary-person content search exists. Full stop. |
| **X / Twitter** | Yes, expensive | API v2 recent search (7 days) on Basic; full archive on Pro | Basic $200/month, Pro $5,000/month. Pay-per-use shipped around February 2026 at roughly $0.005 per read. **The free tier has no read access** and has been read-dead since 2026-02-06. |
| **Spotify** | Barely | Web API search for artists, tracks, playlists | February 2026: search capped at 10 results, user endpoints removed except `/me`. No private listening data. |
| **Podcasts** | Yes | Podcast Index (free, feed-level) plus Listen Notes (full-text episode search) | Podcast Index is $0. Listen Notes free tier is roughly 150 to 300 requests/month, 30 results per query, branding required. |
| **News** | Yes | GDELT (free), NewsAPI (dev free, commercial paid), Exa, TinyFish, Google News RSS | Varies. TinyFish verified at $0.00/call. |
| **Web / SERP** | Yes | Exa, Tavily, SerpApi, Google CSE, SearXNG | Varies. **Bing Search API was retired 2025-08-11**, so that option is gone. |

## What this forced

1. **The news sources named in the original request are the cheapest part, and they were the ones assumed to be hard.** TinyFish is free and GDELT is free, so news retrieval costs nothing. The design default for news is TinyFish at $0.00/call (D7).
2. **X is the expensive one, and it is in the instrument layer only.** At roughly $0.005 per read through treg with the provider pinned, it is workable for personal research and uneconomic as a product read path.
3. **Facebook and WhatsApp are not sources at all.** They are the reason the consented directory exists (D12). This is the single most consequential finding in the research.
4. **Instagram personal accounts are closed.** Only professional accounts are reachable, and only through the instrument layer. A personal Instagram handle comes from the person or not at all.

## Corrections to earlier notes

Three items in the prior research were stale and are corrected here:

- **Google Programmable Search** is closed to new customers and discontinued 2027-01-01. The prior playbook's step 1 depended on it. Dropped (D8).
- **X's free tier** has no read access, and has not since 2026-02-06. Any note describing X as free-to-read is wrong.
- **Threads' unofficial era ended.** `junhoyeo/threads-api` was archived 2023-09-08 after communication from Meta. There is no unofficial Threads path worth maintaining; use the Graph API keyword search or nothing.

## The podcast note

Podcast retrieval is the cheapest and most underrated source here. Podcast Index is free at the feed
level, and the undocumented iTunes `entity=podcastEpisode` recipe (recovered from the 2021 Alias
prototype, see `07-api-recipes.md`) is free and keyless. People who speak publicly appear on
podcasts, and podcast appearance is a strong professional signal that no other source in the list
covers.
