# Legal and ToS boundaries

Researched 2026-10-12 and 2026-10-13. This is the analysis that determines the shape of the
architecture. It is the reason for the `core` / `instrument` split (D3), the reason for no stored
person database (D4), and the reason the consented directory is the product rather than a
nice-to-have (D12).

This is a research record, not legal advice. It records what the sources say and what was decided as
a result.

---

## The single most important fact

**Facebook, WhatsApp, and Instagram handles only ever come from the person.** No API returns them.
No scraper does so reliably. This is not a limitation to work around; it is the constraint that
defines the product. Everything else in this document explains why the surrounding decisions follow
from it.

---

## The layers, and what each is missing

"All of their details" is not a search problem, it is a sourcing problem. Detail is distributed
across layers and each layer is missing a different part.

| Layer | What you get | What is missing | Risk |
|---|---|---|---|
| Official APIs (GitHub, OpenAlex, ORCID, Semantic Scholar, YouTube) | name, affiliation, publications, code, location | email, phone, social handles | none |
| Neural search (Exa people, Perplexity) | public profile text with citations | private contact info | low |
| Commercial brokers (PDL, Apollo, ContactOut) | title, employer, work history, education, sometimes work email | personal socials, usually no phone | medium (GDPR and Decree 13) |
| Scrapers (Apify LinkedIn actors, Bright Data, treg-routed vendors) | full LinkedIn profile: headline, about, experience, skills | Facebook, WhatsApp, Instagram handles | high |
| **Consent (own directory)** | **every field the member chooses to publish** | **nothing** | **none** |

---

## LinkedIn

- **No self-serve people-search API exists.** The standard API returns only the signed-in member's own profile.
- **The Sales Navigator API (SNAP) is closed to new partners.** Not obtainable.
- **hiQ v. LinkedIn:** scraping public pages is not a federal CFAA crime, but LinkedIn won on breach of contract. hiQ ended with a **$500,000 judgment against hiQ Labs plus a permanent injunction**. The lesson is that "not a crime" and "not actionable" are different things, and LinkedIn enforces the contract.
- **Proxycurl (Nubela) was sued by LinkedIn in January 2025** over fake-account scraping, and **shut down in July 2025, deleting its data**. This is the end state of the stored-scraped-people-database business model, and it is the reason D4 exists.
- **Open-source "LinkedIn MCP servers" are almost certainly scrapers** despite "official API" claims in their READMEs. This is why `stickerdaniel/linkedin-mcp-server` lives in `instrument/` and not `core/` even though it is well-built and Apache-2.0 (D17).

**Decided:** LinkedIn is instrument-layer only. Never in a product read path.

---

## Meta (Facebook, Instagram)

- **Meta v. Bright Data:** ToS binds logged-in users. Logged-out scraping of public data was held not to be a contract breach, but Meta blocks it technically and the blocking is effective.
- **Logged-in automation is prohibited**, including Playwright running in your own authenticated session. This is the exact behaviour that is prohibited, not a grey area.
- **The Graph API has no people search.** It serves pages you manage.
- Instagram: professional accounts only, via Business Discovery. Basic Display was retired December 2024.
- Threads: official keyword search exists but needs a permission and has a small, inconsistently-reported quota.

**Decided:** no Facebook source. No WhatsApp source. Instagram in the instrument layer for
professional accounts only. See D12.

---

## Privacy law

Applies to anyone compiling **name plus employer plus contact data**. That is a low bar and this
project clears it by design.

**GDPR / CCPA:**
- Compiling name, employer, and contact information counts as processing personal data.
- Requires a lawful basis, data minimization, and access and deletion rights.

**Vietnam Decree 13/2023:**
- Update 2026-10-17: superseded by the **Personal Data Protection Law No. 91/2025/QH15, effective 2026-01-01** (VERIFY implementing decrees). It is still consent-centric and extraterritorial, so the requirements below remain the design baseline.
- Requires explicit, purpose-specific consent.
- Withdrawal must be honored, and specifically **within 72 hours** in the consented-directory design.
- Breach notification within 72 hours.
- Minors need guardian consent and never appear in the directory.

**Decided:** the consented directory uses an append-only consent log with one entry per purpose
(directory visibility, matching, sharing with a named partner), and a bilingual privacy notice.

---

## The vendor-risk pattern

Every intermediary in this space supplies infrastructure and disclaims the legal question. The user's
exposure does not move.

**Apify** is the clearest example. Its General Terms and Conditions state that Apify supplies
infrastructure only, "shall not be liable for the manner in which you use the Services," cap
liability at 12 months of fees or $1,000, and make a user who breaches a third-party right "fully
liable" and "solely responsible for compensation of any damages." Individual actor publishers add
their own indemnification clauses.

**treg.to** routes per call through named backends (Adyntel, AnyAPI, Apify, Bright Data, ContactOut,
Crawl4AI, Enrichlayer, Fetchin, Fiber AI, HarvestAPI, LeadsForge, LimaData, MoltSets,
ScrapeCreators, TikHub) with **no published privacy policy, retention statement, or compliance
attestation**, and no single controller to serve a deletion request.

**Translation:** buying a call moves the work, not the exposure. The ToS review, the GDPR and
Decree 13 analysis, and the LinkedIn contract question all stay with the user.

---

## The fork: personal tool versus shipped product

These are two different legal objects, and the design addresses both by making the safe core the
whole core.

**As a personal tool**, the latitude is real. Retrieval for one's own networking does not create a
stored database, does not have users, and does not put the operator in the position of a controller
serving deletion requests. The finder stays inside that line by design.

**As a shipped product**, only one design survives:

1. A **retrieve-and-cite search layer** over public sources, with no persistent store. Exa is the working proof that this model is sellable.
2. A **consented directory** for every field no public source returns, above all Facebook, WhatsApp, and Instagram handles.
3. **Scrapers and brokers nowhere in the read path.** They may be the operator's research instruments; they never sit between a user and a stored record.

A product that stores a scraped people database is the Proxycurl path and ends the same way,
regardless of data quality or engineering.

---

## Jurisdiction note

`ap-southeast-1` for anything latency-sensitive to a Vietnamese audience, `us-east-1` otherwise, per
the user's standing AWS convention. This matters for the consented directory more than for the
retrieval core: Decree 13 data-residency expectations attach to stored personal data, and the
retrieval core stores none.
