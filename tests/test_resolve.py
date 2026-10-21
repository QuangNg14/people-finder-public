from __future__ import annotations

from core.models import SourceName as S
from core.resolve import (
    MERGE_THRESHOLD,
    canonical_url,
    dedupe,
    merge_entities,
    merge_score,
    names_match,
    normalize,
    personal_domain,
    rank,
    resolve_identity,
    signals,
)
from tests.helpers import hit, q


def test_same_github_login_from_two_sources_merges() -> None:
    gh = hit(S.GITHUB, "https://github.com/octocat", "The Octocat", login="octocat")
    s2 = hit(
        S.SEMANTIC_SCHOLAR,
        "https://www.semanticscholar.org/author/1",
        "Mona Octocat",
        homepage="https://github.com/octocat",
    )
    entities = resolve_identity([gh, s2])
    assert len(entities) == 1
    assert entities[0].handles["github"] == "octocat"
    assert {h.source for h in entities[0].hits} == {S.GITHUB, S.SEMANTIC_SCHOLAR}


SAME_NAME_DIFFERENT_PEOPLE = [
    # name only
    (
        hit(S.EXA, "https://a.example/1", "John Smith", orgs=["Acme"], location="Austin, TX"),
        hit(S.GITHUB, "https://github.com/jsmith", "John Smith", login="jsmith", company="Globex"),
    ),
    # name plus a shared city is still not enough
    (
        hit(S.EXA, "https://a.example/2", "Maria Garcia", location="Madrid, Spain"),
        hit(S.OPENALEX, "https://openalex.org/A1", "Maria Garcia", location="Madrid, Spain"),
    ),
    # conflicting ORCIDs veto even with a matching org
    (
        hit(
            S.OPENALEX,
            "https://openalex.org/A2",
            "Wei Zhang",
            orcid="https://orcid.org/0000-0001-0000-0001",
            orgs=["Tsinghua University"],
        ),
        hit(
            S.SEMANTIC_SCHOLAR,
            "https://www.semanticscholar.org/author/9",
            "Wei Zhang",
            orcid="https://orcid.org/0000-0002-0000-0002",
            orgs=["Tsinghua University"],
        ),
    ),
    # conflicting GitHub logins veto
    (
        hit(S.GITHUB, "https://github.com/dkim", "David Kim", login="dkim", company="Stripe"),
        hit(S.EXA, "https://github.com/david-kim", "David Kim", orgs=["Stripe"]),
    ),
]


def test_same_name_different_people_do_not_merge() -> None:
    for a, b in SAME_NAME_DIFFERENT_PEOPLE:
        entities = resolve_identity([a, b])
        assert len(entities) == 2, f"false merge: {a.url} + {b.url}"


def test_two_records_from_one_source_never_merge() -> None:
    a = hit(S.GITHUB, "https://github.com/a", "Ann Lee", login="a", company="Acme")
    b = hit(S.GITHUB, "https://github.com/b", "Ann Lee", login="b", company="Acme")
    assert len(resolve_identity([a, b])) == 2


def test_name_plus_org_merges_across_sources() -> None:
    exa = hit(S.EXA, "https://linkedin.com/in/ann", "Ann Lee", orgs=["Acme Inc"])
    gh = hit(S.GITHUB, "https://github.com/annlee", "Ann Lee", login="annlee", company="@acme")
    entities = resolve_identity([exa, gh])
    assert len(entities) == 1 and len(entities[0].hits) == 2


def test_confidence_is_weighted_sum_not_single_threshold() -> None:
    a = signals(hit(S.EXA, "https://x.example/1", "Ann Lee", orgs=["Acme"], location="Hanoi"))
    b = signals(
        hit(
            S.GITHUB,
            "https://github.com/al",
            "Ann Lee",
            login="al",
            company="Acme",
            location="Hanoi, Vietnam",
        )
    )
    c = signals(
        hit(S.GITHUB, "https://github.com/al", "Ann Lee", login="al", location="Hanoi, Vietnam")
    )
    strong = merge_score(a, b)
    weak = merge_score(a, c)
    assert strong > MERGE_THRESHOLD > weak > 0
    assert strong == 0.2 + 0.5 + 0.25


def test_shared_personal_domain_merges_but_platform_hosts_do_not() -> None:
    a = hit(S.GITHUB, "https://github.com/x1", "X One", login="x1", blog="https://xone.dev")
    b = hit(
        S.SEMANTIC_SCHOLAR,
        "https://www.semanticscholar.org/author/5",
        "Xavier One",
        homepage="xone.dev/about",
    )
    assert len(resolve_identity([a, b])) == 1
    assert personal_domain("https://medium.com/@x") is None
    assert personal_domain("someone.github.io") is None


def test_names_match_rules() -> None:
    assert names_match("Geoffrey Hinton", "Geoffrey E. Hinton")
    assert names_match("G. Hinton", "Geoffrey Hinton")
    assert names_match("José Núñez", "Jose Nunez")
    assert not names_match("Geoffrey Hinton", "Geoffrey Holt")
    assert not names_match("Madonna", "Madonna Ciccone")


def test_normalize_and_dedupe() -> None:
    a = hit(
        S.GDELT,
        "http://www.site-a.com/news/1/?utm_source=x#top",
        kind="article",
        title="Big story about a person doing things",
    )
    b = hit(
        S.TINYFISH_NEWS,
        "https://site-a.com/news/1",
        kind="article",
        title="Other title entirely here ok",
    )
    c = hit(
        S.GDELT,
        "https://site-b.com/syndicated",
        kind="article",
        title="Big story about a person doing things",
    )
    out = dedupe(normalize([a, b, c]))
    assert len(out) == 1
    assert canonical_url(a.url) == "http://site-a.com/news/1"


def test_rank_prefers_name_and_org_match() -> None:
    right = hit(S.GITHUB, "https://github.com/r", "Ann Lee", login="r", company="Acme")
    wrong = hit(S.EXA, "https://x.example/w", "Bob Ray", orgs=["Acme"])
    assert rank([wrong, right], q("Ann Lee", org="Acme"))[0] is right


def test_content_attaches_only_to_named_entity() -> None:
    gh = hit(S.GITHUB, "https://github.com/annlee", "Ann Lee", login="annlee")
    repo = hit(
        S.GITHUB,
        "https://github.com/annlee/tool",
        kind="repo",
        title="annlee/tool",
        owner_login="annlee",
    )
    news = hit(S.GDELT, "https://n.example/1", kind="article", title="Ann Lee launches a startup")
    other = hit(S.GDELT, "https://n.example/2", kind="article", title="Unrelated market news")
    [entity] = resolve_identity([gh, repo, news, other])
    assert {h.url for h in entity.hits} == {gh.url, repo.url, news.url}


def test_merge_entities_combines_runs() -> None:
    [e1] = resolve_identity([hit(S.GITHUB, "https://github.com/o", "Oz", login="o")])
    [e2] = resolve_identity([hit(S.EXA, "https://github.com/o", "Oz Person")])
    assert len(merge_entities([e1, e2])) == 1
