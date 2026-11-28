AI Trading Brain (Ai-trading repo, branch feature/grok-autonomous-brain)
Device env: Python 3.14, no Rust toolchain. pydantic v2 / pandas 2.x wheels do not exist for 3.14.
- pandas 3.1.1 + numpy 2.5.5 installed via pkg python-pandas; deps python-dateutil/pytz/tzdata/six via pip --only-binary.
- cryptography distro build present but unusable (missing _cffi_backend), so tests/test_auth_token_flow.py cannot be collected; run it in CI.
- fastapi/pydantic v2 NOT importable -> tests stub fastapi + app.core.auth locally (see tests/test_strategies_api.py, tests/conftest.py).
Test command: python3 -m pytest tests/ -q --ignore=tests/test_auth_token_flow.py  (174 passing as of 2026-02)
