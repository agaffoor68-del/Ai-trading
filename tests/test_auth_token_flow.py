"""Auth route and token persistence regressions; no external services required.

Run with: python -m unittest discover -s tests -v
Install httpx alongside requirements.txt for FastAPI's TestClient.

``cryptography`` and ``fastapi`` are hard requirements (both in
requirements.txt), but neither installs on a bare Python 3.14 without wheels.
The module skips instead of erroring so ``pytest tests/`` stays runnable on a
minimal box; CI installs requirements.txt and therefore runs these tests.
"""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

try:
    from cryptography.fernet import Fernet
    from fastapi.testclient import TestClient
except Exception as _exc:  # pragma: no cover - environment dependent
    pytest.skip(
        f"cryptography/fastapi unavailable ({type(_exc).__name__}: {_exc}); "
        "both are in requirements.txt and run in CI",
        allow_module_level=True,
    )

from app import main
from app.api.v1.endpoints import fyers_auth
from app.core import auth, database
from app.core.models import FyersToken, UserRole


class TokenStorageTests(unittest.TestCase):
    def setUp(self):
        self.fernet = Fernet(Fernet.generate_key())
        self.key_patch = patch.object(fyers_auth, "_fernet", self.fernet)
        self.key_patch.start()
        self.addCleanup(self.key_patch.stop)
        self.session = MagicMock()
        self.session.__enter__.return_value = self.session
        self.session_patch = patch.object(fyers_auth, "SessionLocal", return_value=self.session)
        self.session_patch.start()
        self.addCleanup(self.session_patch.stop)

    def test_save_encrypts_and_commits_token(self):
        self.assertTrue(fyers_auth.save_fyers_token_to_db("access", 3600, "refresh"))
        record = self.session.add.call_args.args[0]
        self.assertIsInstance(record, FyersToken)
        self.assertNotEqual(record.access_token, "access")
        self.assertEqual(self.fernet.decrypt(record.access_token.encode()), b"access")
        self.assertEqual(self.fernet.decrypt(record.refresh_token.encode()), b"refresh")
        self.assertEqual(record.expires_in, 3600)
        self.session.commit.assert_called_once()
        self.session.__exit__.assert_called_once()

    def test_commit_failure_rolls_back_and_closes_session(self):
        self.session.commit.side_effect = RuntimeError("database unavailable")
        with self.assertLogs(fyers_auth.logger, level="ERROR") as logs:
            self.assertFalse(fyers_auth.save_fyers_token_to_db("access", 3600))
        self.session.rollback.assert_called_once()
        self.session.__exit__.assert_called_once()
        self.assertIn("database unavailable (RuntimeError)", "\n".join(logs.output))

    def test_load_decrypts_saved_record(self):
        record = FyersToken(
            access_token=self.fernet.encrypt(b"access").decode(),
            refresh_token=self.fernet.encrypt(b"refresh").decode(),
            expires_in=3600,
            created_at=fyers_auth.now_ist(),
        )
        self.session.query.return_value.order_by.return_value.first.return_value = record
        result = fyers_auth.get_fyers_token_from_db()
        self.assertEqual(result["access_token"], "access")
        self.assertEqual(result["refresh_token"], "refresh")
        self.assertEqual(result["created_at"], record.created_at.isoformat())
        self.session.__exit__.assert_called_once()

    def test_wrong_key_logs_actionable_error_for_empty_invalid_token_exception(self):
        other_key = Fernet(Fernet.generate_key())
        record = FyersToken(access_token=other_key.encrypt(b"access").decode(), expires_in=3600)
        self.session.query.return_value.order_by.return_value.first.return_value = record
        with self.assertLogs(fyers_auth.logger, level="ERROR") as logs:
            self.assertEqual(fyers_auth.get_fyers_token_from_db(), {})
        self.assertIn("InvalidToken", "\n".join(logs.output))
        self.assertIn("TOKEN_ENCRYPTION_KEY", "\n".join(logs.output))

    def test_query_failure_logs_error_and_closes_session(self):
        self.session.query.side_effect = RuntimeError("relation fyers_tokens does not exist")
        with self.assertLogs(fyers_auth.logger, level="ERROR") as logs:
            self.assertEqual(fyers_auth.get_fyers_token_from_db(), {})
        self.assertIn("relation fyers_tokens does not exist", "\n".join(logs.output))
        self.session.__exit__.assert_called_once()


class AuthRouteTests(unittest.TestCase):
    def test_both_me_routes_require_authentication(self):
        client = TestClient(main.app)
        for route in ("/api/auth/me", "/api/v1/auth/me"):
            with self.subTest(route=route):
                self.assertEqual(client.get(route).status_code, 401)

    def test_both_me_routes_resolve_jwt_and_return_user_details(self):
        user = SimpleNamespace(
            id=12, email="user@example.com", role=UserRole.USER,
            is_active=True, subscription=None,
        )
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = user
        main.app.dependency_overrides[auth.get_db] = lambda: db
        self.addCleanup(main.app.dependency_overrides.clear)
        token = auth.create_access_token({"sub": user.email})
        client = TestClient(main.app)
        for route in ("/api/auth/me", "/api/v1/auth/me"):
            with self.subTest(route=route):
                response = client.get(route, headers={"Authorization": f"Bearer {token}"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["email"], user.email)
                self.assertEqual(response.json()["role"], "USER")


class CallbackTests(unittest.TestCase):
    def test_callback_reports_success_only_after_database_commit(self):
        for commit_fails in (False, True):
            with self.subTest(commit_fails=commit_fails):
                state_db, token_db = MagicMock(), MagicMock()
                token_db.__enter__.return_value = token_db
                key = Fernet(Fernet.generate_key())
                state_db.execute.return_value.fetchone.return_value = (
                    key.encrypt(b"client-id").decode(), key.encrypt(b"secret").decode(),
                )
                if commit_fails:
                    token_db.commit.side_effect = RuntimeError("commit failed")
                with (
                    patch.object(fyers_auth, "_fernet", key),
                    patch.object(fyers_auth, "SessionLocal", side_effect=[state_db, token_db]),
                    patch("fyers_apiv3.fyersModel.SessionModel") as sdk,
                    patch.object(fyers_auth, "save_fyers_token") as file_cache,
                    patch.object(fyers_auth.settings, "FYERS_ACCESS_TOKEN", None),
                    patch.object(fyers_auth.settings, "FYERS_CLIENT_ID", None),
                    patch.object(fyers_auth.settings, "FYERS_CLIENT_SECRET", None),
                ):
                    sdk.return_value.generate_token.return_value = {
                        "code": 200, "access_token": "fresh-access", "expires_in": 3600,
                    }
                    response = TestClient(main.app).get(
                        "/api/v1/fyers/callback?auth_code=code&state=state",
                        follow_redirects=False,
                    )
                    token_db.add.assert_called_once()
                    token_db.commit.assert_called_once()
                    self.assertEqual(response.status_code, 307)
                    if commit_fails:
                        token_db.rollback.assert_called_once()
                        self.assertIn("reason=token_storage_error", response.headers["location"])
                        file_cache.assert_not_called()
                        self.assertIsNone(fyers_auth.settings.FYERS_ACCESS_TOKEN)
                    else:
                        self.assertIn("fyers=connected", response.headers["location"])
                        self.assertEqual(fyers_auth.settings.FYERS_ACCESS_TOKEN, "fresh-access")


class StartupTests(unittest.TestCase):
    def test_init_db_creates_registered_token_table(self):
        with (
            patch.object(database.Base.metadata, "create_all") as create_all,
            patch.object(database.engine, "connect"),
        ):
            database.init_db()
        create_all.assert_called_once_with(bind=database.engine)
        self.assertIn("fyers_tokens", database.Base.metadata.tables)

    def test_startup_stops_when_database_initialization_fails(self):
        with (
            patch.object(main, "init_db", side_effect=RuntimeError("schema unavailable")),
            patch.object(main, "seed_admin_user") as seed,
        ):
            with self.assertRaisesRegex(RuntimeError, "schema unavailable"):
                asyncio.run(main.startup_event())
        seed.assert_not_called()


if __name__ == "__main__":
    unittest.main()
