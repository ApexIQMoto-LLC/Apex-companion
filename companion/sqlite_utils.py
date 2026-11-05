"""Transactional SQLite context that also closes connections on Windows.

Unlike sqlite3.Connection.__exit__, this helper releases the file handle.
It commits on success, rolls back on exceptions, and is safe for test tempdirs.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator


@contextmanager
def open_sqlite(path: str | Path, **kwargs) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(path, **kwargs)
    try:
        with connection:
            yield connection
    finally:
        connection.close()
