"""Import smoke test: every non-HTTP module must import cleanly.

A dependency install can succeed while the application still dies on startup
because a module imports something that does not exist (the ``pandas_ta`` case)
or references a name that is not defined.  This walks the real package and
imports each module, so that class of failure is caught before deployment.

Modules that need a live database, network or credentials are still imported —
importing does not connect — but any module that raises is reported with the
exact exception.
"""

from __future__ import annotations

import importlib
import pkgutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# app/api/** and app/main.py need FastAPI + pydantic v2, which are stubbed only
# partially in this environment; they are covered by the dedicated API tests.
SKIP_PREFIXES = ("app.api", "app.main")


def _modules():
    import app

    names = []
    for info in pkgutil.walk_packages(app.__path__, prefix="app."):
        if info.name.startswith(SKIP_PREFIXES):
            continue
        names.append(info.name)
    return sorted(names)


def test_every_module_is_discovered():
    names = _modules()
    assert len(names) > 40, f"expected the whole package, found {len(names)}"


def _declared_modules():
    """Top-level module names provided by requirements.txt.

    Used to tell "this dependency is declared but not installed on this box"
    (skip) apart from "this module does not exist at all" (fail).  The latter
    is what broke startup before, e.g. pandas_ta and
    app.services.indicator_engine.
    """
    names = set()
    for line in ROOT.joinpath("requirements.txt").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        dist = line.split("==")[0].split(">=")[0].split("[")[0].strip()
        if not dist:
            continue
        module = dist.lower().replace("-", "_")
        names.add(module)
        # python-foo -> foo (python-jose -> jose, python-dateutil -> dateutil)
        if module.startswith("python_"):
            names.add(module[len("python_"):])
    return names


DECLARED = _declared_modules()


@pytest.mark.parametrize("module_name", _modules())
def test_module_imports(module_name):
    """Importing must not raise (no missing dependency, no bad name)."""
    try:
        importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        missing = (exc.name or "").split(".")[0]
        if missing in DECLARED:
            pytest.skip(f"{missing} is in requirements.txt but not installed here")
        raise


def test_no_module_imports_a_phantom_dependency():
    """Guard the pandas_ta / app.services.indicator_engine regression."""
    offenders = []
    for path in ROOT.joinpath("app").rglob("*.py"):
        source = path.read_text(errors="ignore")
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import pandas_ta", "from pandas_ta")):
                offenders.append(f"{path.name}: {stripped}")
            if stripped.startswith(
                ("from app.services.indicator_engine", "import app.services.indicator_engine")
            ):
                offenders.append(f"{path.name}: {stripped}")
    assert offenders == [], offenders
