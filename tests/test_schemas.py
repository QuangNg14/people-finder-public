"""The product-path schemas have no field for the forbidden categories (phase 10, spec 19)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from core.models import Claim, Entity, Hit

SCHEMAS = Path(__file__).resolve().parent.parent / "schemas"
FORBIDDEN = (
    "phone",
    "mobile",
    "address",
    "street",
    "postcode",
    "zip",
    "birth",
    "dob",
    "age",
    "gender",
    "religion",
    "ethnic",
    "race",
    "health",
    "sexual",
    "orientation",
    "political",
    "biometric",
    "union",
    "message",
    "ssn",
    "passport",
    "salary",
)


def _forbidden(key: str) -> bool:
    tokens = key.lower().replace("-", "_").split("_")
    return any(tok.startswith(bad) for tok in tokens for bad in FORBIDDEN)


def _keys(node: Any) -> list[str]:
    out: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "properties" and isinstance(v, dict):
                out.extend(v.keys())
            out.extend(_keys(v))
    elif isinstance(node, list):
        for v in node:
            out.extend(_keys(v))
    return out


def _closed(node: Any) -> list[bool]:
    out: list[bool] = []
    if isinstance(node, dict):
        if "properties" in node:
            out.append(node.get("additionalProperties") is False)
        for v in node.values():
            out.extend(_closed(v))
    elif isinstance(node, list):
        for v in node:
            out.extend(_closed(v))
    return out


@pytest.mark.parametrize("name", ["person.schema.json", "consent.schema.json"])
def test_schema_has_no_forbidden_fields_and_is_closed(name: str) -> None:
    schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    for key in _keys(schema):
        assert not _forbidden(key), f"{name}: {key}"
    assert all(_closed(schema)), f"{name}: every object must set additionalProperties false"


def test_runtime_models_have_no_forbidden_fields() -> None:
    for model in (Hit, Claim, Entity):
        for field in model.__dataclass_fields__:
            assert not _forbidden(field), f"{model.__name__}.{field}"


def test_forbidden_matcher_catches_real_violations() -> None:
    assert _forbidden("phone_number") and _forbidden("home_address") and _forbidden("ethnicity")
    assert not _forbidden("languages") and not _forbidden("response_indicator")
