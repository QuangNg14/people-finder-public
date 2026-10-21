# Prior art: Discord-Job-Crawl-Server

Source: `Discord-Job-Crawl-Server/`

A Discord bot that scrapes eight job boards, normalises and dedupes the results, caches them in
MongoDB, and posts to a channel. It is the closest thing to this project that already exists in the
user's own code, and it is the **pattern donor for the core** (D14).

**Port the patterns, not the code.** The crawler is JavaScript, the core is Python, and the crawler's
Mongo dependency is forbidden here (D4, D14). What transfers is the shape of four things.

---

## 1. The source registry

`Discord-Job-Crawl-Server/scrape.js`, the `availableScrapers` dict:

```javascript
const availableScrapers = {
  linkedin: {
    name: "LinkedIn",
    scraper: (client) =>
      linkedinScraper.scrapeAllJobs(
        config.linkedin.timeFilters.week,
        client,
        "comprehensive"
      ),
  },
  ziprecruiter: { name: "ZipRecruiter", scraper: (client) => ... },
  jobright:     { name: "JobRight",     scraper: (client) => ... },
  github:       { name: "GitHub",       scraper: (client) => ... },
};
```

Each module is self-contained and exports a narrow surface:

```javascript
// scrapers/linkedin.js
module.exports = { scrapeAllJobs };

// scrapers/github.js
module.exports = { scrapeAllJobs, scrapeSpecificRepo, scrapeRepository, scrapeGithubRepo };
```

**What transfers:** a registry dict where each entry names a module and a callable, and each module
knows nothing about any other module. In this project that becomes `SOURCES: dict[SourceName, Source]`
in `core/sources/base.py`, populated by decorator so adding a source is one file plus one line
(spec section 6).

**What does not transfer:** the arrow functions capture `client` and `config` at registry-definition
time, which means the registry has to be read to know what a source is actually called with. The
`Source` protocol fixes this by putting the parameters in `SourceQuery` where they belong.

---

## 2. Normalise, dedupe, rank

`Discord-Job-Crawl-Server/utils/helpers.js` exports:

```
generateJobId, normalizeJob, deduplicateJobs, sortJobsByRelevance,
formatJobForDiscord, createDiscordJobMessages, createDailySummaryMessage,
createSourceSummaryMessages, sendSourceSummaryToDiscord,
isRelevantJob, filterRelevantJobs, filterJobsByDate, delay
```

The pipeline is: **normalize, then dedupe, then sort by relevance, then filter by recency.** Every
scraper produces its own shape, `normalizeJob` flattens them into one, `deduplicateJobs` removes
cross-source repeats, and the relevance and date filters decide what is worth keeping.

**What transfers:** the shape of the pipeline and the identity idea behind it. In this project:
`normalize(hits) -> dedupe(hits) -> rank(hits, q)` in `core/resolve.py`, with `resolve_identity`
doing the person-specific version of what `deduplicateJobs` does for jobs.

**What is different, and why it matters:** deduplicating jobs is easy because a job has a real
identity (company, title, location, often a canonical posting ID). Deduplicating **people** is not,
because two people share a name and two profiles of one person share almost nothing. This is the
single hardest problem in this project and the crawler's `normalizedId` idea only gets partway
there. Hence the two-source rule (D15), which is a deliberate refusal to solve the problem with a
similarity threshold.

---

## 3. The cache with a fallback path

`Discord-Job-Crawl-Server/services/mongo.js` exports:

```
connect, loadCache, loadSourceCache, getFileCachePath, jobExists,
jobExistsByNormalizedId, getRecentJobs, getAllRecentJobs, shouldSkipSource,
addJobs, saveToFile, clearCache, clearAllCaches, getCacheStats, getAllCacheStats,
pruneCache, close, getJobsFromSource, isConnected
```

Schema: per-source collection, `createIndex({ jobId: 1 }, { unique: true })`, plus a `normalizedId`
for cross-source dedupe.

Three functions carry the important idea:

- `jobExists` and `jobExistsByNormalizedId` are two levels of identity: an exact repeat, and a cross-source repeat.
- `shouldSkipSource` is the quota-protection guard.
- `saveToFile` / `getFileCachePath` is the file fallback when Mongo is unreachable.

**What transfers:** the two-level identity check, and `shouldSkipSource` as the pattern for "this
source is exhausted or failing, skip it rather than hammer it." Both appear in `core/cache.py` and
`core/http.py`.

**What does not transfer:** MongoDB. Fourteen exported functions do what one SQLite table with four
columns does here (spec section 9), and running a database server to cache HTTP responses is
infrastructure without a reason. The **file fallback** idea survives in spirit: the cache must
degrade rather than fail, which is the same instinct as per-source isolation (D18).

---

## 4. The deployable container

`Discord-Job-Crawl-Server/Dockerfile`: `node:22-slim`, Chromium
installed, a non-root `pptr` user, a healthcheck on `/health`, and a `MODE`-driven `start.sh` with
`daily` / `daily-now` / `scrape` / `server` modes, deployable to Azure Container Instances.

**What transfers:** the MODE-driven entrypoint, the non-root user, the healthcheck, and resource
limits. If the core ever needs to run unattended, this is the shape.

**What does not transfer, and it is deliberate:** Chromium, `puppeteer`, and
`puppeteer-extra-plugin-stealth`. Those exist in the crawler because job boards are scraped. Browser
automation is instrument-layer work (D3, D14) and appears in this project only in `instrument/`, if
at all. The core has no browser.

---

## 5. Configuration

`Discord-Job-Crawl-Server/config.js` top-level keys:

```
channelId, debugMode, scrapingSchedule, dailyScraping, mongo, antiDetection,
puppeteer, jobFiltering, linkedin, ziprecruiter, jobright, github,
enhancedScrapingTargets, mcpPuppeteer, messageSummarization, logging
```

One config module with a per-source section is a good pattern and is reused: this project reads
per-source settings (keys, TTLs, rate limits, batch sizes) from one place rather than scattering them
through source modules.

**What is dropped:** the `antiDetection`, `mongo`, and `puppeteer` trees. They configure things the
core does not do.

---

## Summary of what to port

| Pattern | Where it lands |
|---|---|
| Source registry dict, self-contained modules | `core/sources/base.py`, `SOURCES` |
| normalize, dedupe, rank pipeline | `core/resolve.py` |
| Two-level identity check (exact plus normalized) | `core/cache.py`, `core/resolve.py` |
| Quota-protection skip guard | `core/http.py` |
| Cache degrades to a fallback rather than failing | `core/cache.py` |
| MODE-driven container, non-root, healthcheck | deployment, when unattended runs exist |
| One config module with per-source sections | project configuration |

| Anti-pattern | Why it stays behind |
|---|---|
| MongoDB for a cache | One SQLite table does the job. D14 |
| Chromium and stealth plugins in the core | Instrument-layer concern. D3, D14 |
| Anti-detection configuration | Nothing in the core is being detected against |
| Registry lambdas capturing ambient scope | Replaced by the `Source` protocol and `SourceQuery` |
