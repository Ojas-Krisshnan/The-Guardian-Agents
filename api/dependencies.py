# api/dependencies.py
"""Service dependency injection container."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from slice.config import Settings, settings
from slice.store import Store

_GLOBAL_STORE: Store | None = None


def get_db_path() -> Path:
    return Path(settings().database_path)


def get_store() -> Store:
    global _GLOBAL_STORE
    if _GLOBAL_STORE is None:
        _GLOBAL_STORE = Store(get_db_path())
        from synapse.database import init_domain_tables
        init_domain_tables(_GLOBAL_STORE.db)
        from api.auth import ensure_seed_data
        ensure_seed_data(_GLOBAL_STORE.db)
    return _GLOBAL_STORE


def set_store(store: Store) -> None:
    global _GLOBAL_STORE
    _GLOBAL_STORE = store
    from synapse.database import init_domain_tables
    init_domain_tables(_GLOBAL_STORE.db)
    from api.auth import ensure_seed_data
    ensure_seed_data(_GLOBAL_STORE.db)


def get_settings_dep() -> Settings:
    return settings()
