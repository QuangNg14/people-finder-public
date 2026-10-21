"""core/ must be importable and functional with instrument/ deleted (spec 4.1)."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _imports(path: Path) -> list[str]:
    names: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
            names.extend(alias.name for alias in node.names)
    return names


def test_core_never_imports_instrument() -> None:
    files = list((ROOT / "core").rglob("*.py"))
    assert files, "core/ has no modules"
    for path in files:
        for name in _imports(path):
            assert "instrument" not in name, f"{path} imports {name}"


def test_core_mcp_server_never_imports_instrument() -> None:
    for name in _imports(ROOT / "mcp" / "people_core.py"):
        assert "instrument" not in name


def test_wheel_excludes_instrument() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    hatch = config["tool"]["hatch"]["build"]["targets"]
    assert hatch["wheel"]["packages"] == ["core"]
    assert "instrument" in hatch["sdist"]["exclude"]
    assert "instrument" not in hatch["sdist"]["include"]


def test_boundary_check_detects_a_violation(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text("from instrument.linkedin import search\n", encoding="utf-8")
    assert any("instrument" in n for n in _imports(bad))
