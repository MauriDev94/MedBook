"""Test settings for MedBook.

Extends base.py with production-faithful PostgreSQL testing.

Official test runs MUST use PostgreSQL, locally and in CI. Do not fall back to
SQLite here: SQLite can hide migration/schema issues that PostgreSQL catches.
"""

import os
from pathlib import Path

import dj_database_url

from .base import *  # noqa: F403, F401

# ---------------------------------------------------------------------------
# Load .env.test here — NOT in conftest.py.
#
# pytest-django imports settings via its own pytest_configure plugin hook,
# which runs BEFORE conftest.py hooks. Loading here guarantees DATABASE_URL
# is available when dj_database_url.config() is evaluated below.
# ---------------------------------------------------------------------------
_env_file = Path(__file__).resolve().parent.parent.parent / ".env.test"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _key, _, _val = _line.partition("=")
        os.environ.setdefault(_key.strip(), _val.strip())
del _env_file

# ---------------------------------------------------------------------------
# Debug
# ---------------------------------------------------------------------------
DEBUG = True

# ---------------------------------------------------------------------------
# Database — PostgreSQL by default
# ---------------------------------------------------------------------------
# Local and CI should use the same database engine to avoid false-green tests.
# Override DATABASE_URL when your local credentials differ.
DATABASES = {
    "default": dj_database_url.config(
        default="postgres://postgres@localhost:5436/medbook_test",
        conn_max_age=600,
    )
}

# ---------------------------------------------------------------------------
# Faster password hashing
# ---------------------------------------------------------------------------
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# ---------------------------------------------------------------------------
# Email backend
# ---------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
