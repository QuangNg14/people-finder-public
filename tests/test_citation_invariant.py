"""An uncited Claim is unconstructable (spec 5.1, D5)."""

from __future__ import annotations

import dataclasses

import pytest

from core.models import Claim, SourceName, utcnow


def _claim(**overrides: object) -> Claim:
    kwargs: dict[str, object] = {
        "field": "current_role",
        "value": "CEO at X",
        "source_url": "https://example.com/about",
        "source_name": SourceName.EXA,
        "retrieved_at": utcnow(),
        "confidence": 0.9,
    }
    kwargs.update(overrides)
    return Claim(**kwargs)  # type: ignore[arg-type]


def test_claim_without_source_url_raises() -> None:
    with pytest.raises(TypeError):
        Claim("current_role", "CEO")  # type: ignore[call-arg]


def test_source_url_has_no_default() -> None:
    field = next(f for f in dataclasses.fields(Claim) if f.name == "source_url")
    assert field.default is dataclasses.MISSING
    assert field.default_factory is dataclasses.MISSING


@pytest.mark.parametrize("url", ["", "   ", "example.com", "ftp://example.com", None])
def test_claim_rejects_non_http_url(url: object) -> None:
    with pytest.raises(ValueError):
        _claim(source_url=url)


def test_claim_rejects_empty_value_and_bad_confidence() -> None:
    with pytest.raises(ValueError):
        _claim(value="  ")
    with pytest.raises(ValueError):
        _claim(confidence=1.5)


def test_valid_claim_is_frozen() -> None:
    claim = _claim()
    with pytest.raises(dataclasses.FrozenInstanceError):
        claim.source_url = "https://other.example"  # type: ignore[misc]
