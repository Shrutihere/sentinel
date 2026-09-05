"""Test config — point Sentinel at an isolated throwaway SQLite DB.

Must run before `sentinel` is imported so the engine binds to the test DB. pytest
imports conftest first, and we set the env var at import time here.
"""

import os
import tempfile

_test_db = os.path.join(tempfile.gettempdir(), "sentinel_test.db")
if os.path.exists(_test_db):
    os.remove(_test_db)
os.environ["SENTINEL_DATABASE_URL"] = f"sqlite:///{_test_db}"
