"""Every third-party import in the deployed app must be declared in requirements.txt.

Regression guard for the Render crash
``ModuleNotFoundError: No module named 'httpx'``
(app/main.py -> app/api/v1/endpoints/brain.py ->
 app/services/brain/decision_engine.py -> app/services/grok_service.py -> httpx).

The check is static (AST), so it needs no dependency installed and no network:
it fails on the *next* undeclared import instead of on the first deploy that
happens to touch that code path.

Scope is the deployed package ``app/`` plus ``app/main.py``.  The legacy
root-level ``backend/`` and ``indicator_engine.py`` scripts are not imported by
the ASGI app and are intentionally out of scope.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
REQUIREMENTS = ROOT / "requirements.txt"

# Import name -> distribution name, only where they differ.
MODULE_ALIASES = {
    "dotenv": "python-dotenv",
    "jose": "python-jose",
    "multipart": "python-multipart",
    "pydantic_settings": "pydantic-settings",
    "fyers_apiv3": "fyers-apiv3",
    "email_validator": "email-validator",
    "pyotp": "pyotp",
    "httpx": "httpx",
}

# First-party / local modules that are not pip dependencies.
LOCAL_MODULES = {
    "app",
    "api",
    "backend",
    "services",
    "tests",
    "main",
    "indicator_engine",
    "gen_hooks",
    "project_config",
}


def declared_modules() -> set[str]:
    """Top-level import names provided by requirements.txt."""
    names: set[str] = set()
    for raw in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        dist = line.split("==")[0].split(">=")[0].split("<=")[0].split("[")[0].strip()
        if not dist:
            continue
        module = dist.lower().replace("-", "_")
        names.add(module)
        if module.startswith("python_"):
            names.add(module[len("python_") :])
    return names


DECLARED = declared_modules()


def iter_third_party_imports():
    """Yield (module, file, line) for every non-stdlib, non-local import."""
    stdlib = set(sys.stdlib_module_names)
    for path in sorted(APP_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top and top not in stdlib and top not in LOCAL_MODULES:
                        yield top, path, node.lineno
            elif isinstance(node, ast.ImportFrom):
                if node.level or not node.module:
                    continue
                top = node.module.split(".")[0]
                if top not in stdlib and top not in LOCAL_MODULES:
                    yield top, path, node.lineno


def test_requirements_file_is_readable():
    assert REQUIREMENTS.is_file(), "requirements.txt is missing"
    assert DECLARED, "requirements.txt declares no dependencies"


def test_httpx_is_declared():
    """The exact dependency whose absence crashed Render."""
    assert "httpx" in DECLARED


def test_every_import_is_declared():
    offenders: list[str] = []
    for module, path, lineno in iter_third_party_imports():
        distribution = MODULE_ALIASES.get(module, module)
        if module in DECLARED or distribution in DECLARED:
            continue
        offenders.append(f"{path.relative_to(ROOT)}:{lineno} imports {module!r}")

    assert not offenders, (
        "undeclared third-party imports (add them to requirements.txt):\n  "
        + "\n  ".join(sorted(offenders))
    )


def test_no_undeclared_imports_in_new_modules():
    """Parametrised view of the same rule, one test id per offending module."""
    modules = sorted({module for module, _, _ in iter_third_party_imports()})
    assert modules, "no imports discovered - the walker is broken"
    for module in modules:
        distribution = MODULE_ALIASES.get(module, module)
        if module not in DECLARED and distribution not in DECLARED:
            pytest.fail(f"{module} is imported under app/ but not in requirements.txt")
