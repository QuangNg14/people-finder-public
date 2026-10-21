# Index

Read order for someone picking this up cold. The design doc is self-contained; the research and
decisions docs are what make it defensible rather than arbitrary, and they are where you go when a
design choice looks wrong.

| # | Document | Read it when |
|---|---|---|
| 1 | [`README.md`](/README.md) | First. What this is, status, keys, hard rules. |
| 2 | [`superpowers/specs/2026-10-14-people-finder-design.md`](/docs/superpowers/specs/2026-10-14-people-finder-design.md) | Second. The complete design: architecture, data model, sources, testing, degradation. |
| 3 | [`decisions.md`](/docs/decisions.md) | Before changing the design. Almost everything that looks missing was decided against on purpose. |
| 4 | [`roadmap.md`](/docs/roadmap.md) | When you are ready to write code. Ten phases, each with acceptance criteria. |
| 5 | [`open-questions.md`](/docs/open-questions.md) | Before making a commitment the docs do not cover. |
| 6 | [`research/01-platform-reality.md`](/docs/research/01-platform-reality.md) | When someone asks "why not just pull from X/Instagram/Facebook." |
| 7 | [`research/02-legal-boundaries.md`](/docs/research/02-legal-boundaries.md) | Before anything ships, or before adding any source that is not an official API. |
| 8 | [`research/03-source-evaluation.md`](/docs/research/03-source-evaluation.md) | Before adding or swapping a source, or before spending money on one. |
| 9 | [`research/04-github-landscape.md`](/docs/research/04-github-landscape.md) | When evaluating an open-source tool to pull in. |
| 10 | [`research/05-prior-art-alias.md`](/docs/research/05-prior-art-alias.md) | When wondering what the 2021 codebase still contributes. |
| 11 | [`research/06-prior-art-job-crawler.md`](/docs/research/06-prior-art-job-crawler.md) | Before building the source registry, the dedupe layer, or the Docker image. |
| 12 | [`research/07-api-recipes.md`](/docs/research/07-api-recipes.md) | When implementing the podcast sources. Two working recipes live here and nowhere else. |
| 13 | [`research/08-alias-revival-2026-10.md`](research/08-alias-revival-2026-10.md) | When deciding whether and how to continue the Alias concept: Follow, footprint pages, claimed pages, and what must not come back. |

## The compressed version

If you read nothing else: the product-safe core retrieves from official APIs and Exa, holds no
database, and refuses to emit an uncited claim. Scrapers exist in a separate package that the core
cannot import. Facebook, WhatsApp, and Instagram handles come only from the person, which is why a
consented directory is the eventual product and not an afterthought. The core is free to run.
