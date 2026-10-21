# API recipes

Working, verified recipes with the specific gotchas that cost time. Two of these were recovered from
the 2021 Alias prototype and exist nowhere in the public documentation.

---

## 1. iTunes episode search (undocumented, keyless)

**The single most reusable thing recovered from Alias.** The blog post's own note: "This API is
**not** in the documentation and it took me a long time to figure it out."

```
GET https://itunes.apple.com/search?term=<url-encoded title>&entity=podcastEpisode
```

No key. No auth. Returns a JSON object whose `results[0].trackViewUrl` is the Apple Podcasts episode
URL when the episode exists.

```python
async def search_episode(title: str) -> str | None:
    """Resolve an Apple Podcasts episode URL from an episode title. Keyless."""
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://itunes.apple.com/search",
            params={"term": title, "entity": "podcastEpisode"},
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        return results[0]["trackViewUrl"] if results else None
```

**Gotchas:**
- The `entity=podcastEpisode` parameter is the whole trick. Without it, `term` searches podcasts, not episodes, and returns the show rather than the episode.
- The match is title-based and fuzzy. Record the title you queried alongside the result so a wrong resolution is traceable rather than silent.
- Throttle in batches of 15 with a 10-second delay between batches (the Alias prototype's constant). Gentler than it needs to be, which is the right default for an undocumented endpoint.
- A missing episode is normal, not an error. Return `None` and let the caller decide.

---

## 2. Spotify episode search (client credentials)

Retained for reference. **Not adopted as a source**, because Spotify capped search to 10 results in
February 2026 and removed user endpoints (D7, `03-source-evaluation.md`). The iTunes route above is
keyless and better for episode resolution.

Step 1, get a token:

```
POST https://accounts.spotify.com/api/token
Content-Type: application/x-www-form-urlencoded
Authorization: Basic base64(<client_id>:<client_secret>)

body: grant_type=client_credentials
```

Step 2, search for the episode:

```
GET https://api.spotify.com/v1/search?q=<url-encoded title>&type=episode&market=US
Authorization: Bearer <access_token>
```

Read `episodes.items[0].external_urls.spotify`.

**Gotchas:**
- The credentials belong in the environment, never in the code.
- Batch 50 with a 5-second delay between batches (the prototype's constant).
- The `market` parameter is required for episode search. `US` is what the prototype used; a Vietnamese target audience would want `VN` considered.
- Tokens expire in 3600 seconds. Cache the token and refresh on 401, rather than requesting one per call.

---

## 3. The two-step podcast pattern

The shape Alias used and the shape this project adopts: **discover episodes from a feed-level index,
then resolve canonical URLs per platform.**

1. Discover: Podcast Index (adopted, free) returns feed-level podcast and episode metadata. Listen Notes (deferred) does full-text episode search.
2. Resolve: for each discovered episode title, call the iTunes recipe above to get the canonical Apple Podcasts URL.

**Why two steps:** a feed-level index tells you an episode exists and who is on it; per-platform
search tells you where to link it. Neither does the other's job, and the resolution step is free and
keyless.

---

## 4. GitHub: gzip and emoji

Not an API recipe so much as a bug that will be reintroduced if it is not written down.

GitHub returns gzip-compressed responses, and repository and profile descriptions carry emoji. Two
concrete consequences:

- Send `Accept-Encoding: gzip` and decompress. `httpx` does this automatically when the header is present and the response is handled normally; if you build the request manually, do not forget it.
- The prior build additionally needed a UTF-8 stdout reconfigure, because emoji in descriptions broke printing on the Windows console. On Python 3.13 with an explicit encoding on output this is less likely, but if a source prints mojibake, this is why.

```python
# The prior build needed this for emoji in GitHub descriptions on Windows
sys.stdout.reconfigure(encoding="utf-8")
```

---

## 5. GitHub rate limits, concretely

| Auth | General | Search |
|---|---|---|
| None | 60 req/hour | 10 req/min |
| Token | 5,000 req/hour | 30 req/min |

Search is the binding constraint and it is a separate budget from general requests. Profile
enrichment (`GET /users/{login}`) is one request per person, so enriching 100 people costs 100
general requests, which is why an unauthenticated build runs out fast. Bulk scraping beyond these
limits is barred by GitHub's terms.

---

## 6. Exa people

```
POST https://api.exa.ai/search
Authorization: Bearer <EXA_API_KEY>

{ "query": "<name or description>", "category": "people", "numResults": 10 }
```

`category:"people"` returns structured person entities rather than page links: `name`, `location`,
`workHistory[]`, `educationHistory[]`, and `research` with `hIndex` and notable works. It indexes
roughly 1B professional profiles refreshed weekly.

**Gotchas:**
- `category:"news"` is a separate category at a higher price. Do not use it as the default news route; TinyFish is free (D7).
- The cost is $0.004/call and it draws down the $10/month resetting credit, which is roughly 2,500 searches/month.
- An earlier design draft also asserted a singular `category:"person"` for single-entity fetch. **That was not verified and was removed.** Confirm during phase 3 (`open-questions.md` item 4).
- Websets is a different, richer product surface (per-field citations and confidence ratings) that needs a paid plan. Not adopted; see `open-questions.md` item 1.

---

## 7. OpenAlex polite pool

Not a key, an email:

```
GET https://api.openalex.org/authors?filter=...
User-Agent: mailto:<OPENALEX_EMAIL>
```

The polite pool gets faster and more reliable service for the cost of an email address in the
User-Agent. OpenAlex's free-versus-metered status is unresolved (`03-source-evaluation.md`); send the
`mailto` either way.

---

## 8. Batch throttling constants

Carried from the Alias prototype because they are reasonable starting points, not because they are
optimal. Tune per source in `core/http.py`.

| Source | Batch | Delay | Notes |
|---|---|---|---|
| iTunes | 15 | 10s | Undocumented endpoint, be gentle |
| Spotify | 50 | 5s | Reference only |
| GitHub Search | 10 | 60s | Solves to 30/min authed; the delay is the reliable control |
| Semantic Scholar | 1 | 1s | Keyless 429s by the third call, so keyless mode needs a longer delay or a key |

---

## 9. The MCP registration quirks

Two things that cost time on the Windows build and will cost time again:

- **Servers load at session startup.** A new `claude mcp add-json` registration does not appear in the current session. Restart.
- **Windows paths in `claude mcp add-json` must use forward slashes.** A backslash-escaped Windows path is rejected with `Invalid configuration: : Invalid input`. Use `C:/Users/.../server.py`, not `C:\\Users\\...`.

```bash
claude mcp add-json people-core -s user \
  '{"type":"stdio","command":"uv","args":["run","--directory","/path/to/people-finder","python","mcp/people_core.py"]}'
```
