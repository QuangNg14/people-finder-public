from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from core.__main__ import main
from core.dossier import build_dossier, dossier
from core.models import Entity, SourceName
from core.page import render_markdown
from core.resolve import resolve_identity
from tests.conftest import load
from tests.helpers import hit


def _sample_dossier() -> object:
    profile = hit(
        SourceName.GITHUB,
        "https://github.com/annlee",
        "Ann [Lee]",
        login="annlee",
        company="Acme | Labs",
        location="Hanoi",
    )
    paper = hit(
        SourceName.OPENALEX,
        "https://doi.org/10.1/x",
        kind="publication",
        title="A paper",
        venue="NeurIPS",
        published="2026-05-01",
        match="identifier",
    )
    repo = hit(
        SourceName.GITHUB,
        "https://github.com/annlee/tool",
        kind="repo",
        title="annlee/tool",
        owner_login="annlee",
        published="2026-02-01",
    )
    [entity] = resolve_identity([profile, repo])
    # Identifier-anchored content joins via dossier._with_content, not name-based attachment.
    entity = Entity(
        display_name=entity.display_name,
        handles=entity.handles,
        claim_count=entity.claim_count + 1,
        score=entity.score,
        hits=[*entity.hits, paper],
    )
    other = Entity(
        display_name="Ann Lee",
        handles={},
        claim_count=1,
        score=0.2,
        hits=[hit(SourceName.EXA, "https://example.org/ann-chef", "Ann Lee")],
    )
    return build_dossier(
        entity,
        [SourceName.YOUTUBE],
        source_status={"youtube": "missing_key (set YOUTUBE_API_KEY)", "github_repos": "ok"},
        alternates=[other],
    )


def test_render_cites_every_item_and_escapes() -> None:
    d = _sample_dossier()
    md = render_markdown(d)  # type: ignore[arg-type]
    assert md.startswith("# Ann \\[Lee\\]")
    assert "## Papers" in md and "## Code" in md
    assert "[A paper (NeurIPS, 2026-05-01)](<https://doi.org/10.1/x>)" in md
    assert "Acme \\| Labs" in md
    for line in md.splitlines():
        if line.startswith("- ") and "and " not in line[:6]:
            assert "](<http" in line, line
    assert "## Not this person?" in md and "https://example.org/ann-chef" in md
    assert "Unavailable or empty: youtube: missing_key" in md
    assert "Content lookups: github_repos: ok." in md


def test_identifier_content_gets_full_confidence() -> None:
    d = _sample_dossier()
    by_field = {c.field: c for c in d.claims}  # type: ignore[attr-defined]
    assert by_field["publication"].confidence > by_field["github_repo"].confidence


def test_dossier_adds_papers_and_repos_by_identifier() -> None:
    with respx.mock(assert_all_called=False) as router:
        router.get("https://api.openalex.org/authors").mock(
            return_value=httpx.Response(200, json=load("openalex_authors.json"))
        )
        works = router.get("https://api.openalex.org/works").mock(
            return_value=httpx.Response(200, json=load("openalex_works.json"))
        )
        d = dossier("Geoffrey Hinton", sources=(SourceName.OPENALEX,))
    assert "author.id:A5108093963" in works.calls.last.request.url.params["filter"]
    papers = [c for c in d.claims if c.field == "publication"]
    assert papers and all(c.source_url != "https://openalex.org/A5108093963" for c in papers)
    assert any(c.source_url.startswith("https://doi.org/") for c in papers)
    assert d.source_status["openalex_works"] == "ok"

    with respx.mock(assert_all_called=False) as router:
        router.get("https://api.github.com/search/users").mock(
            return_value=httpx.Response(200, json=load("github_search_users.json"))
        )
        router.get(url__regex=r"https://api\.github\.com/users/[^/]+$").mock(
            return_value=httpx.Response(200, json=load("github_user_torvalds.json"))
        )
        router.get("https://api.github.com/users/torvalds/repos").mock(
            return_value=httpx.Response(200, json=load("github_user_repos.json"))
        )
        d2 = dossier("torvalds", sources=(SourceName.GITHUB,), limit=3)
    repos = {c.source_url for c in d2.claims if c.field == "github_repo"}
    assert "https://github.com/torvalds/AudioNoise" in repos
    assert "https://github.com/torvalds" not in repos


def test_cli_page_writes_only_with_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with respx.mock(assert_all_called=False) as router:
        router.route().mock(return_value=httpx.Response(200, json={}))
        assert main(["page", "Nobody Atall"]) == 0
        assert list(tmp_path.iterdir()) == []
        assert "# Nobody Atall" in capsys.readouterr().out
        out = tmp_path / "page.md"
        assert main(["page", "Nobody Atall", "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("# Nobody Atall")


def test_cli_whats_new_requires_one_selector() -> None:
    with pytest.raises(SystemExit):
        main(["whats-new", "--since", "2026-01-01"])
