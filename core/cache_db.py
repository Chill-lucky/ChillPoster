from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager

from core.configs import MEDIA_LIBRARY_CACHE_FILE


CACHE_DB_FILE = (
    os.getenv("CHILLPOSTER_CACHE_DB")
    or os.getenv("CHILLPOSTER_MEDIA_LIBRARY_CACHE_DB")
    or os.path.splitext(MEDIA_LIBRARY_CACHE_FILE)[0] + ".db"
)


def get_cache_db_file() -> str:
    return CACHE_DB_FILE


def open_cache_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(CACHE_DB_FILE), exist_ok=True)
    conn = sqlite3.connect(CACHE_DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


@contextmanager
def cache_db(write: bool = False):
    conn = open_cache_connection()
    try:
        if write:
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        if write:
            conn.commit()
    except Exception:
        if write:
            conn.rollback()
        raise
    finally:
        conn.close()
