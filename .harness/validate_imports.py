"""Import-validate the real FastAPI app on this phone (no workspace changes).

pydantic v2 / cryptography / aiohttp cannot be built on this device (no Rust
toolchain, no manylinux wheels for Android arm64), so the pydantic stub from
tests/conftest.py is reused.  Everything else -- httpx, fastapi, sqlalchemy,
passlib, jose, fyers -- is the real installed package, which is exactly what
the Render crash was about.

Run:  PYTHONPATH="$HARNESS_SCRATCH/deps" python .harness/validate_imports.py
"""
import os
import pathlib
import sys
import tempfile
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

_DB = pathlib.Path(tempfile.gettempdir()) / "importcheck.db"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///" + str(_DB)
os.environ["ENVIRONMENT"] = "test"

import conftest  # noqa: F401,E402  installs pydantic/pydantic_settings stubs only

import httpx  # noqa: E402

print("httpx", httpx.__version__, "->", httpx.__file__)

MODULES = [
    "app.services.grok_service",
    "app.services.brain.decision_engine",
    "app.api.v1.endpoints.brain",
    "app.main",
]

failures = 0
for name in MODULES:
    try:
        __import__(name)
        print("OK   ", name)
    except Exception:
        failures += 1
        print("FAIL ", name)
        traceback.print_exc()

if not failures:
    import app.main as main_module

    print("routes:", len(main_module.app.routes))
    print("title :", main_module.app.title)

sys.exit(1 if failures else 0)
