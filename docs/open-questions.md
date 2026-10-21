# Open questions

What is genuinely unresolved, separated from what was resolved during the design session. Each entry
names its owner: **user** means a decision that is not mine to make, **implementation** means it can
be settled with code or a live call during the build.

Anything not listed here is decided. See `decisions.md`.

---

## 1. Exa plan: free tier or paid? (owner: user)

The free tier includes a $10/month credit that resets monthly, which at $0.004 per people search is
about 2,500 searches per month. That comfortably covers personal use.

**Recommendation:** stay on the free tier and revisit at 1,000 searches/month of actual usage.
There is no case for paying before the pattern is proven, and the credit does not expire, so
early usage is free either way.

**What would change the answer:** wanting Websets (the per-field-cited collection API) rather than
the `category:"people"` vertical. Websets needs a paid plan to use its API at all (roughly $49/month
Starter), and the free plan caps a webset at 25 results. Websets is the better product surface and
the worse value at personal volume, so this is only worth revisiting if the tool is being shipped.

---

## 2. OpenAlex free-versus-metered (owner: implementation)

Official OpenAlex documentation states that OpenAlex data is free, including casual API use. A
third-party source claims OpenAlex became key-required and credit-metered in February 2026. These do
not reconcile, and the reported pricing page 404s.

**Recommendation:** treat OpenAlex as free, register for a free key anyway (it costs nothing and
covers the metered case if it exists), and send a `mailto` in the User-Agent for the polite pool.
Handle a credit-exhaustion or 402 response as a normal degradation path rather than a crash.

**Resolve it during phase 4** with one live keyless call and one live keyed call, and record the
result in `research/03-source-evaluation.md`.

---

## 3. Muse web_search pricing discrepancy (owner: implementation)

Meta's documentation states $2.50 per 1,000 searches. A third-party tracker reports $0.00825 per
executed query. $2.50/1,000 is $0.0025/query, so the two figures differ by roughly 3x.

This does not change the Muse decision, because Muse is rejected on capability (no people vertical),
not on price. It matters only if anyone revisits Muse as a general web-search source, which would
need the price settled first.

**Recommendation:** leave it. Re-check at `dev.meta.ai/docs/pricing-rate-limits` only if Muse comes
back into scope.

---

## 4. Exa `category:"person"` singular (owner: implementation)

The design uses `category:"people"`. An earlier draft also asserted a `category:"person"` singular
for single-entity fetch; that was removed during self-review because it was not verified.

**Recommendation:** confirm against the live Exa docs during phase 3. If a single-entity fetch
exists, use it for the dossier planner to avoid re-ranking a list. If not, filter the list result
locally.

---

## 5. Vault correction: Muse description and Google PSE (owner: user)

Outside this repository, but it will mislead the next session that reads the vault.

- `<private vault>/Pathwise Resources/13-concept-synthesis/playbooks/networking-people-search.md` line 27 describes Meta Muse as "a separate consumer personal-agent product, not a developer people-search API." The second clause is correct; the first is stale, since Muse models are now callable on the Meta Model API (though still not a people source, per D9).
- The same playbook's step 1 depends on Google Programmable Search Engine, which is closed to new customers and discontinued 2027-01-01 (D8). The step needs replacing with Exa's people vertical.
- The `log.md` entry dated 2026-10-12 repeats the same stale Muse description.

**Recommendation:** correct all three in one editing pass. The playbook is `audience: mentor` and
the vault has its own schema requirements (frontmatter, index and log updates, no em dashes), so
this is a deliberate separate task rather than a drive-by edit.

---

## 6. Repo visibility (resolved)

The core, the MCP server, the schemas and the docs are public. The dev/test-only `instrument/`
layer, which reaches platforms whose terms forbid automated access, is not part of the public
repository.

---

## 7. Email verification for the consented directory (owner: user, deferred)

The consented-directory design (spec section 17) specifies corporate work-email magic link as the
primary verification method, mirroring Blind and PeopleGrove. That implies a transactional email
provider when the directory is built.

**Recommendation:** defer entirely. The directory is a product-path concern and nothing in phases 0
to 10 needs it. Named here only so it is not discovered as a surprise later. Note that the Pathwise
codebase already has consent and deletion prior art (`services/account_service.py`, migration 024's
ledger tombstone) if the directory is ever built.
