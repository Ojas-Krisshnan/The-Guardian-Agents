"""API Dependencies."""
from __future__ import annotations

import os
from typing import Generator

from slice.config import Settings, settings
from slice.store import Store


def get_settings() -> Settings:
    """Return project configuration settings."""
    return settings()


def get_db_path() -> str:
    """Return database path from environment configuration, defaulting to 'run.db'."""
    return os.environ.get("SLICE_DB", "run.db")


def get_store() -> Generator[Store, None, None]:
    """Dependency yielding a Store instance connected to the configured database."""
    db_path = get_db_path()
    store = Store(db_path)
    try:
        yield store
    finally:
        store.close()
