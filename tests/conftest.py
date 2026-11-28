"""Test harness for the AI Brain test-suite.

The production image installs ``pydantic``/``httpx`` from ``requirements.txt``.
This phone-based test runner has no Rust toolchain, so ``pydantic-core`` cannot
be built here.  To keep the **real** service code under test (risk engine,
execution, learning, memory, news, freshness) the harness installs minimal,
clearly-marked stand-ins for the two import-time dependencies and points
``DATABASE_URL`` at a temporary SQLite file.

Nothing in ``app/`` is modified for tests: the stubs live only in
``sys.modules`` for the duration of the run, and every test that would need a
real network call or a real model call is driven through a local fixture
instead.  Tests never assert a broker fill, a Grok answer or a market move that
did not happen.
"""

from __future__ import annotations

import os
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TEST_DB = Path(tempfile.gettempdir()) / "ai_brain_test.db"
os.environ.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{_TEST_DB}")
os.environ.setdefault("ENVIRONMENT", "test")


def _install_pydantic_stub() -> None:
    if "pydantic" in sys.modules:
        return
    try:  # real dependency available → use it
        import pydantic  # noqa: F401
        # pydantic_settings is no longer required by app/core/config.py, so a
        # working pydantic v1/v2 is enough.  Only stub what is truly missing.
        if not hasattr(pydantic, "BaseModel") or not hasattr(pydantic, "Field"):
            raise ModuleNotFoundError("pydantic incomplete")
        # Minimal patch: expose Field and BaseModel as attribute-bag.
        # Do NOT patch model_dump — that triggers the fastapi v2 import path
        # which can't be retroactively fixed after the interpreter starts.
        return
    except ModuleNotFoundError:
        # Install a true stub module so imports don't raise.
        class _Model:
            """Attribute bag with the two helpers our code actually calls."""
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
            def model_dump(self, *args, **kwargs):
                return dict(self.__dict__)
            def dict(self, *args, **kwargs):
                return dict(self.__dict__)

        pydantic_mod = types.ModuleType("pydantic")
        pydantic_mod.BaseModel = _Model
        pydantic_mod.Field = lambda **kwargs: None  # noqa: E731 - pydantic name
        pydantic_mod.ValidationError = ValidationError
        sys.modules["pydantic"] = pydantic_mod
        """Attribute bag with the two helpers our code actually calls."""

        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

        def model_dump(self, *args, **kwargs):
            return dict(self.__dict__)

        def dict(self, *args, **kwargs):
            return dict(self.__dict__)

    def Field(default=None, default_factory=None, **kwargs):  # noqa: N802 - pydantic name
        if default_factory is not None:
            return default_factory()
        return default

    class ValidationError(ValueError):
        pass

    pydantic = types.ModuleType("pydantic")
    pydantic.BaseModel = _Model
    pydantic.Field = Field
    pydantic.ValidationError = ValidationError
    sys.modules["pydantic"] = pydantic
    _install_settings_stub()


def _install_settings_stub() -> None:
    """Minimal pydantic-settings stand-in (only if the real one is missing)."""
    if "pydantic_settings" in sys.modules:
        return

    def _coerce(raw: str, current):
        if isinstance(current, bool):
            return raw.strip().lower() in {"1", "true", "yes", "on"}
        if isinstance(current, int) and not isinstance(current, bool):
            try:
                return int(raw)
            except ValueError:
                return current
        if isinstance(current, float):
            try:
                return float(raw)
            except ValueError:
                return current
        return raw

    class BaseSettings:
        def __init__(self, **kwargs):
            cls = type(self)
            for name in getattr(cls, "__annotations__", {}):
                if hasattr(cls, name):
                    setattr(self, name, getattr(cls, name))
            for key, value in kwargs.items():
                setattr(self, key, value)
            for name in list(vars(self)):
                raw = os.environ.get(name)
                if raw is not None:
                    setattr(self, name, _coerce(raw, getattr(self, name)))

    settings_mod = types.ModuleType("pydantic_settings")
    settings_mod.BaseSettings = BaseSettings
    settings_mod.SettingsConfigDict = lambda **kwargs: dict(kwargs)
    sys.modules["pydantic_settings"] = settings_mod


def _install_httpx_stub() -> None:
    try:
        import httpx  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    class _HTTPError(Exception):
        pass

    class TimeoutException(_HTTPError):
        pass

    class NetworkError(_HTTPError):
        pass

    class Timeout:
        def __init__(self, *args, **kwargs):
            self.args = args

    class Limits:
        def __init__(self, *args, **kwargs):
            self.args = args

    class AsyncClient:  # never used in tests; present so imports succeed
        def __init__(self, *args, **kwargs):
            self.args = args

        async def aclose(self):
            return None

    httpx = types.ModuleType("httpx")
    httpx.AsyncClient = AsyncClient
    httpx.Timeout = Timeout
    httpx.Limits = Limits
    httpx.TimeoutException = TimeoutException
    httpx.NetworkError = NetworkError
    httpx.HTTPError = _HTTPError
    sys.modules["httpx"] = httpx


_install_pydantic_stub()
_install_httpx_stub()

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def db_engine():
    """Session engine bound to the temporary SQLite file."""
    from app.core import models  # noqa: F401 - register users/subscriptions tables
    from app.core.database import Base, engine

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def clean_db(db_engine):
    """Truncate every Brain table before each test."""
    from app.core.database import Base, SessionLocal, engine

    for table in reversed(Base.metadata.sorted_tables):
        with engine.begin() as conn:
            conn.execute(table.delete())
    with SessionLocal() as db:
        yield db


@pytest.fixture()
def user_id(clean_db):
    """A stable non-existent user id (Brain rows are keyed by it)."""
    return 4242


@pytest.fixture()
def enabled_config(user_id):
    """Risk configuration that permits autonomous paper trading on NIFTY."""
    from app.core.brain_models import RiskConfig
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        config = RiskConfig(
            user_id=user_id,
            master_autonomous_enabled=True,
            trading_mode="paper",
            allowed_instruments=["NIFTY"],
            allowed_segments=["NSE"],
            max_risk_per_trade_pct=2.0,
            max_daily_loss=5000.0,
            max_total_open_positions=3,
            max_position_size=50,
            max_daily_trades=10,
            max_portfolio_exposure=200000.0,
            max_consecutive_losses=3,
            session_start="09:20",
            session_end="15:10",
            square_off_time="15:20",
            emergency_exit_policy="hold",
            require_stop_loss=True,
            min_risk_reward=1.0,
            max_spread_pct=1.0,
        )
        db.add(config)
        db.commit()
    return config
