# GitHub landscape

The open-source ecosystem around people search and OSINT, surveyed 2026-10-13. Two parts: the
high-star repository survey, and the verdicts on specific GitHub accounts that were raised in the
original request.

---

## Part 1: the people-search and OSINT ecosystem

Ranked by stars on 2026-10-13. Verdicts use the same integrate / study / use-as-map / avoid scale as
the rest of the research.

| Repo | Stars | License | What it does | Verdict |
|---|---|---|---|---|
| `sherlock-project/sherlock` | 94.1k | MIT | find a username across many social networks | STUDY |
| `koala73/worldmonitor` | 88.4k | AGPL-3.0 | real-time global intelligence dashboard | not relevant |
| `bilawalsidhu/gods-eye-view` | 54.8k | custom | spy satellite simulator, real data | not relevant |
| `soxoj/maigret` | 38.9k | MIT | dossier on a person by username, 6k sites | STUDY |
| `lissy93/web-check` | 35.1k | MIT | analyse any website | STUDY |
| `jivoi/awesome-osint` | 30.2k | custom | the canonical curated OSINT index | USE as the map |
| `qeeqbox/social-analyzer` | 24.3k | AGPL-3.0 | profile lookup across 1000 sites | STUDY |
| `smicallef/spiderfoot` | 23.4k | MIT | automated OSINT recon | STUDY |
| `laramies/theHarvester` | 17.9k | GPL-2.0 | emails, subdomains, names for an org | USE for org recon |
| `antoniaci/blackbird` | 9.1k | none | username and email across 600+ sites | STUDY |
| `lanmaster53/recon-ng` | 6.0k | GPL-3.0 | OSINT framework | STUDY |
| `khast3x/h8mail` | 5.3k | custom | email OSINT and breach hunting | AVOID (breach data) |
| `joeyism/linkedin_scraper` | 4.6k | GPL-3.0 | LinkedIn profile scraping library | AVOID |
| `speedyapply/JobSpy` | 4.5k | MIT | job-board scraper, LinkedIn included | jobs only, not people |
| `Astrosp/Awesome-OSINT-List` | 4.5k | GPL-3.0 | OSINT tool index | USE as the map |
| `rawfilejson/awesome-osint-arsenal` | 3.2k | MIT | 100+ tool installer bundle | STUDY |
| `martinvigo/email2phonenumber` | 2.8k | MIT | infers a phone number from an email | **AVOID** |
| `cporter202/social-media-scraping-apis` | 2.5k | none | curated social scraping API list | reference only |
| `megadose/ignorant` | 2.1k | GPL-3.0 | checks if a phone number is registered on sites | **AVOID** |
| `dchrastil/ScrapedIn` | 1.2k | none | LinkedIn scraping without API limits | AVOID |
| `l4rm4nd/LinkedInDumper` | 616 | none | dumps company employees from LinkedIn | AVOID |
| `soxoj/awesome-osint-mcp-servers` | 509 | MIT | curated OSINT MCP servers | USE as the map |

### Reading across the list

The strong, well-maintained projects are **username enumeration** and **organisation recon**. Those
are worth studying and `theHarvester` is directly useful for org-level recon.

Everything pointed at LinkedIn profiles is either stale (last pushed 2022 to 2024), unlicensed, or a
direct repeat of the Proxycurl mistake. `joeyism/linkedin_scraper`, `dchrastil/ScrapedIn`, and
`l4rm4nd/LinkedInDumper` are all the same idea that ended in a lawsuit.

**`email2phonenumber` and `ignorant` are a category apart and are excluded on principle, not on
risk.** They infer a phone number the subject never published. That is stalking tooling, and the
project's own rules (no phone numbers, no inferred sensitive traits) exclude them before any legal
analysis is needed.

---

## Part 2: the named GitHub accounts

These five accounts were raised explicitly in the original request. They came from a request about
YouTube tooling and general utilities, not people search, so most are out of scope for this project.
Recorded so the assessment is not repeated.

| Account | Notable repos | Theme | Verdict |
|---|---|---|---|
| `grqz` | yt-dlp fork (146 stars, active yt-dlp contributor), `yt-dlp-getpot-jsi` (49, Apache-2.0), `yt-dlp-apple-webkit-jsi`, `ssl_imp` (52), `aes` (46) | PO-token anti-bot plugins for yt-dlp; Chrome TLS fingerprint impersonation; constant-time educational AES | **INTEGRATE** the yt-dlp plugins; **LEARN FROM** `ssl_imp` and `aes` |
| `yuliskov` | SmartTube (34.9k, MIT, active), SharedModules | ad-free Android TV YouTube client on YouTube's private API | LEARN FROM only (YouTube ToS grey area) |
| `TheMythologist` | `obsidian-plugin-create-folder-same-directory` (0BSD), GenP (4.2k), `android-cracker` (99, LGPL) | Obsidian QoL plugin; Adobe crack builder; lock-screen brute forcer | **INTEGRATE** the Obsidian plugin only; **AVOID** GenP and `android-cracker` |
| `WitherOrNot` | StartXBack (256), MuseDashDLCUnlock (231), `warbird-docs`, `cbs-docs`, `chacha`, `how-to-activate-windows-*`, `cbsexploder`, `uupget`, `winkeycheck` | software cracks, DLC piracy, Windows/KMS licensing bypass | **AVOID entirely** |
| `stevietv` | Boot.dev and Odin Project exercises | personal coursework | not useful, no risk |

### Why these verdicts

- **`grqz` is the only account with something this project can use.** The yt-dlp PO-token plugins matter if YouTube blocks the reference-video ingest step, which is a video-pipeline concern rather than a people-search one. Pin the version. Personal device only.
- **`yuliskov/SmartTube`** is a reference for metadata and caption extraction patterns, and nothing else. It builds on YouTube's private API, which is a ToS grey area.
- **`TheMythologist`** publishes one useful Obsidian plugin among piracy tooling. Take the plugin; leave the rest.
- **`WitherOrNot`** is licensing bypass and piracy end to end. Nothing here is usable, and on a work device or account, Windows activation bypass is a direct employer-policy problem in addition to everything else. Do not clone or reference these repositories.
- **`stevietv`** is coursework. No value, no risk.

None of these accounts matters for people search. The relevant open-source finding is `stickerdaniel/linkedin-mcp-server` (D17), which was selected on its own merits, plus the curator repos
(`jivoi/awesome-osint`, `soxoj/awesome-osint-mcp-servers`) as maps of the space.

---

## Part 3: what the survey establishes

1. **The mature open-source work is in identity enumeration and org recon, not in profile retrieval.** That is a useful signal: the maintainable problems are the ones without a platform actively fighting them.
2. **Every LinkedIn-targeted tool is either abandoned, unlicensed, or legally radioactive.** The pattern is consistent enough to treat as a rule.
3. **The phone-number-inference tools are excluded before the legal analysis.** The project's data model has no field for a phone number, so they cannot contribute even if they were permitted.
4. **The curated index repos are more valuable than any single tool.** `jivoi/awesome-osint` and `soxoj/awesome-osint-mcp-servers` are where to look when a new source is needed.
