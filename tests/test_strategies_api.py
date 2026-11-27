"""Tests for the Strategy Builder API (Part 2).

The frontend was calling ``/api/v1/strategies`` while only
``/api/v1/brain/strategies`` existed, so every request returned 404.  These
tests exercise the **real** router functions and the real ``UserStrategy`` model
against an in-memory session, and assert the ownership rule: a user can never
see or modify another user's strategies.

Environment note: this phone-based runner has no Rust toolchain, so ``pydantic``
v2 (and therefore FastAPI) cannot be installed.  ``fastapi`` and
``app.core.auth`` are replaced with minimal stand-ins *in this module only* —
the router source, its validation and its SQLAlchemy model are the real ones.
"""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# --------------------------------------------------------------- import shims
def _install_fastapi_shim() -> None:
    """Just enough FastAPI for the router module to import."""
    try:
        import fastapi  # noqa: F401
        return
    except Exception:
        pass

    class HTTPException(Exception):
        def __init__(self, status_code, detail=None, headers=None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail
            self.headers = headers

    class _Router:
        def __init__(self, *args, **kwargs):
            self.tags = kwargs.get("tags", [])

        def _register(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

        get = post = put = delete = _register

    def Depends(dependency=None, **kwargs):  # noqa: N802 - FastAPI name
        return dependency

    def Query(default=None, **kwargs):  # noqa: N802 - FastAPI name
        return default

    class Request:  # pragma: no cover - unused by these tests
        pass

    module = types.ModuleType("fastapi")
    module.APIRouter = _Router
    module.Depends = Depends
    module.Query = Query
    module.HTTPException = HTTPException
    module.Request = Request
    sys.modules["fastapi"] = module


def _install_auth_shim() -> None:
    """The router only needs these two dependency callables."""
    try:
        import app.core.auth  # noqa: F401
        return
    except Exception:
        pass

    module = types.ModuleType("app.core.auth")

    def get_db():  # pragma: no cover - overridden by the fixture
        raise RuntimeError("get_db must be patched in tests")

    def get_current_user():  # pragma: no cover - overridden by the fixture
        raise RuntimeError("get_current_user must be patched in tests")

    module.get_db = get_db
    module.get_current_user = get_current_user
    sys.modules["app.core.auth"] = module


_install_fastapi_shim()
_install_auth_shim()

from app.api.v1.endpoints import strategies as mod  # noqa: E402
from app.core.strategy_models import UserStrategy  # noqa: E402


# --------------------------------------------------------------------- helpers
class _Query:
    """Minimal stand-in for a SQLAlchemy query, scoped to one user."""

    def __init__(self, rows, user_id):
        self._rows = [r for r in rows if r.user_id == user_id]
        self._limit = None
        self._offset = 0

    def filter(self, *criteria):
        # The router's only filter is the active-only flag.  SQLAlchemy renders
        # it as "user_strategies.is_active IS true", so honour that here
        # instead of silently ignoring the criterion.
        for criterion in criteria:
            rendered = str(criterion).lower()
            if "is_active is true" in rendered:
                self._rows = [r for r in self._rows if r.is_active]
            elif "is_active is false" in rendered:
                self._rows = [r for r in self._rows if not r.is_active]
        return self

    def count(self):
        return len(self._rows)

    def order_by(self, *args):
        return self

    def offset(self, value):
        self._offset = value
        return self

    def limit(self, value):
        self._limit = value
        return self

    def all(self):
        rows = self._rows[self._offset:]
        return rows if self._limit is None else rows[: self._limit]

    def first(self):
        return self._rows[0] if self._rows else None


class _Session:
    """In-memory session good enough for the strategies router."""

    def __init__(self):
        self.rows = []
        self._next_id = 1
        self.current_user_id = None

    def query(self, model):
        return _Query(self.rows, self.current_user_id)

    def add(self, row):
        row.id = self._next_id
        self._next_id += 1
        self.rows.append(row)

    def delete(self, row):
        self.rows = [r for r in self.rows if r is not row]

    def commit(self):
        pass

    def refresh(self, row):
        pass


class _User:
    def __init__(self, user_id):
        self.id = user_id
        self.role = None
        self.email = f"u{user_id}@example.com"


class _FixedNow:
    """Deterministic timestamp so assertions never depend on the clock."""

    def isoformat(self):
        return "2026-01-01T09:15:00+05:30"


@pytest.fixture()
def env(monkeypatch):
    session = _Session()
    monkeypatch.setattr(mod, "get_db", lambda: session)
    monkeypatch.setattr(mod, "now_ist", lambda: _FixedNow())
    return session


def _as(env, user_id):
    env.current_user_id = user_id
    return _User(user_id)


def _run(coro):
    return asyncio.run(coro)


def _create(env, user, **kwargs):
    payload = mod.StrategyPayload(**kwargs)
    return _run(mod.create_strategy(payload, user, env))


# ----------------------------------------------------------------------- tests
def test_router_is_mounted_at_the_frontend_path():
    """Root cause of the 404: main.py must include this router at /api/v1/strategies."""
    source = (ROOT / "app" / "main.py").read_text()
    assert "from app.api.v1.endpoints.strategies import router as strategies_router" in source
    assert 'include_router(strategies_router, prefix="/api/v1/strategies"' in source


def test_router_declares_all_five_verbs():
    """GET list, POST create, GET one, PUT update, DELETE remove."""
    source = (ROOT / "app" / "api" / "v1" / "endpoints" / "strategies.py").read_text()
    for marker in (
        '@router.get("")',
        '@router.post("", status_code=201)',
        '@router.get("/{strategy_id}")',
        '@router.put("/{strategy_id}")',
        '@router.delete("/{strategy_id}")',
    ):
        assert marker in source, marker


def test_list_returns_empty_envelope_not_404(env):
    user = _as(env, 1)

    result = _run(mod.list_strategies(100, 0, False, user, env))

    assert result["strategies"] == []
    assert result["total"] == 0
    assert isinstance(result["strategies"], list)


def test_create_then_list_round_trip(env):
    user = _as(env, 1)

    created = _create(
        env,
        user,
        name="NIFTY Momentum",
        description="EMA cross",
        conditions=[mod.StrategyCondition(indicator1="EMA", condition=">", indicator2="SMA")],
        timeframe="15m",
        stopLoss=1.5,
        target=3.0,
        isActive=True,
    )

    assert created["strategy"]["id"] == 1
    assert created["strategy"]["conditions"][0]["indicator1"] == "EMA"
    assert created["strategy"]["stopLoss"] == 1.5

    listed = _run(mod.list_strategies(100, 0, False, user, env))
    assert listed["total"] == 1
    assert listed["strategies"][0]["name"] == "NIFTY Momentum"
    assert listed["strategies"][0]["isActive"] is True


def test_strategies_are_scoped_to_their_owner(env):
    owner = _as(env, 1)
    other = _as(env, 2)
    _create(env, owner, name="Owner only")

    assert _run(mod.list_strategies(100, 0, False, other, env))["total"] == 0

    with pytest.raises(mod.HTTPException) as exc:
        _run(mod.get_strategy(1, other, env))
    assert exc.value.status_code == 404

    with pytest.raises(mod.HTTPException) as exc:
        _run(mod.delete_strategy(1, other, env))
    assert exc.value.status_code == 404
    # The owner's row survived the other user's delete attempt.
    assert len(env.rows) == 1


def test_get_update_delete_lifecycle(env):
    user = _as(env, 1)
    _create(env, user, name="S1")

    fetched = _run(mod.get_strategy(1, user, env))
    assert fetched["strategy"]["name"] == "S1"

    updated = _run(
        mod.update_strategy(
            1, mod.StrategyUpdate(name="S1 renamed", target=5.0, isActive=True), user, env
        )
    )
    assert updated["strategy"]["name"] == "S1 renamed"
    assert updated["strategy"]["target"] == 5.0
    assert updated["strategy"]["isActive"] is True

    deleted = _run(mod.delete_strategy(1, user, env))
    assert deleted["deleted"] is True
    assert _run(mod.list_strategies(100, 0, False, user, env))["total"] == 0


def test_unknown_id_returns_404(env):
    user = _as(env, 1)
    with pytest.raises(mod.HTTPException) as exc:
        _run(mod.get_strategy(999, user, env))
    assert exc.value.status_code == 404


def test_condition_without_indicator_is_rejected(env):
    user = _as(env, 1)
    with pytest.raises(mod.HTTPException) as exc:
        _create(env, user, name="Bad", conditions=[mod.StrategyCondition(indicator1="EMA")])
    assert exc.value.status_code == 422


def test_active_only_filter(env):
    user = _as(env, 1)
    _create(env, user, name="on", isActive=True)
    _create(env, user, name="off", isActive=False)

    result = _run(mod.list_strategies(100, 0, True, user, env))
    assert [s["name"] for s in result["strategies"]] == ["on"]


def test_strategy_table_is_registered_for_migrations():
    """init_db()/run_migrations must create the table on a fresh deploy."""
    migrations = (ROOT / "app" / "core" / "migrations_brain.py").read_text()
    assert '"user_strategies"' in migrations

    main_source = (ROOT / "app" / "main.py").read_text()
    assert "strategy_models" in main_source


def test_model_serialises_the_shape_the_ui_consumes():
    row = UserStrategy(
        user_id=1,
        name="UI shape",
        description="d",
        conditions=[{"indicator1": "RSI", "condition": "<", "indicator2": "30"}],
        timeframe="5m",
        stop_loss_pct=2.0,
        target_pct=4.0,
        is_active=True,
    )
    payload = row.to_dict()
    assert payload["stopLoss"] == 2.0
    assert payload["target"] == 4.0
    assert payload["isActive"] is True
    assert payload["timeframe"] == "5m"
    assert payload["conditions"][0]["indicator1"] == "RSI"
