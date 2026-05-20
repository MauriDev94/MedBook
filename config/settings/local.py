"""Local development settings for MedBook.

Extends base.py with PostgreSQL via DATABASE_URL and debug-friendly config.
"""
import dj_database_url
from decouple import config

from .base import *  # noqa: F403, F401

# ---------------------------------------------------------------------------
# Debug
# ---------------------------------------------------------------------------
DEBUG = True

# ---------------------------------------------------------------------------
# Database — PostgreSQL via DATABASE_URL (leído desde .env por python-decouple)
# ---------------------------------------------------------------------------
DATABASE_URL = config(
    "DATABASE_URL",
    default="postgres://postgres:postgres@localhost:5432/medbook",
)
DATABASES = {
    "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600),
}
