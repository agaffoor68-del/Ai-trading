"""Boot the real ASGI app and hit /info + /health (no workspace changes).

Local box limits (documented, not worked around in the repo):
  * pydantic 2 / pydantic-core, cryptography, aiohttp, psycopg-binary have no
    Android-aarch64 wheels and need a Rust/C toolchain that is not installed,
    so pydantic 1.10 + fastapi 0.115.8 (the version pinned in
    requirements.txt) are used with a 3-line pydantic_settings shim.
  * DATABASE_URL points at a temporary SQLite file because no PostgreSQL
    server exists here; app/core/database.py only rewrites postgres:// URLs.

Run:  PYTHONPATH="$HARNESS_SCRATCH/deps" python .harness/boot_check.py
"""
import os
import pathlib
import sys
import tempfile
import threading
import time
import types
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///" + str(
    pathlib.Path(tempfile.gettempdir()) / "bootcheck.db"
)
os.environ["ENVIRONMENT"] = "test"
os.environ.setdefault("BRAIN_ENABLED", "false")

# --- local-only shims (pydantic v1 box) -------------------------------------
import pydantic  # noqa: E402

if not hasattr(pydantic, "ConfigDict"):
    pydantic.ConfigDict = lambda **kwargs: dict(kwargs)

if "pydantic_settings" not in sys.modules:
    try:
        import pydantic_settings  # noqa: F401
    except ModuleNotFoundError:
        settings_mod = types.ModuleType("pydantic_settings")

        class BaseSettings(pydantic.BaseModel):
            """Minimal stand-in: field defaults overridden by env vars."""

            def __init__(self, **kwargs):
                for name in type(self).__fields__:
                    if name in kwargs:
                        continue
                    raw = os.environ.get(name.upper(), os.environ.get(name))
                    if raw is not None:
                        kwargs[name] = raw
                super().__init__(**kwargs)

        settings_mod.BaseSettings = BaseSettings
        settings_mod.SettingsConfigDict = lambda **kwargs: dict(kwargs)
        sys.modules["pydantic_settings"] = settings_mod

# --- import + serve ---------------------------------------------------------
# cryptography ships no Android aarch64 wheel and its Rust binding cannot be
# built here, so only the two names app/api/v1/endpoints/fyers_auth.py imports
# are faked.  python-jose falls back to its native backend automatically.
if "cryptography" not in sys.modules:
    crypto = types.ModuleType("cryptography")
    crypto.__path__ = []  # makes submodule imports fail -> jose uses native
    fernet_mod = types.ModuleType("cryptography.fernet")

    class InvalidToken(Exception):
        pass

    class Fernet:  # only instantiated with a real key at runtime
        def __init__(self, key):
            self.key = key

    fernet_mod.Fernet = Fernet
    fernet_mod.InvalidToken = InvalidToken
    crypto.fernet = fernet_mod
    sys.modules["cryptography"] = crypto
    sys.modules["cryptography.fernet"] = fernet_mod

import uvicorn  # noqa: E402

from app.main import app  # noqa: E402

print("app import OK:", app.title, "routes:", len(app.routes))

config = uvicorn.Config(app, host="127.0.0.1", port=8011, log_level="warning")
server = uvicorn.Server(config)
thread = threading.Thread(target=server.run, daemon=True)
thread.start()

status = None
for _ in range(60):
    if server.started:
        break
    time.sleep(0.5)

for path in ("/info", "/health"):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:8011{path}", timeout=5) as response:
            body = response.read().decode()[:220]
            print(f"GET {path} -> {response.status} {body}")
            if path == "/info":
                status = response.status
    except Exception as error:  # noqa: BLE001
        print(f"GET {path} -> ERROR {type(error).__name__}: {error}")

server.should_exit = True
thread.join(timeout=15)
print("server.started:", server.started, "| /info status:", status)
sys.exit(0 if status == 200 else 1)
