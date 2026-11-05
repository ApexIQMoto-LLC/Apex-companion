"""Regression tests for transactional SQLite connections on Windows."""
import tempfile
import unittest
from pathlib import Path

from companion.sqlite_utils import open_sqlite


class SqliteFileHandleTests(unittest.TestCase):
    def test_connection_is_closed_before_temp_directory_cleanup(self):
        # On Windows an open sqlite3 file handle prevents TemporaryDirectory cleanup.
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "closed.sqlite3"
            with open_sqlite(path) as conn:
                conn.execute("CREATE TABLE items(value INTEGER NOT NULL)")
                conn.execute("INSERT INTO items(value) VALUES (1)")
            with open_sqlite(path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
            self.assertEqual(count, 1)
        self.assertFalse(path.exists())

    def test_transaction_rolls_back_and_connection_closes_on_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rollback.sqlite3"
            with open_sqlite(path) as conn:
                conn.execute("CREATE TABLE items(value INTEGER NOT NULL)")
            with self.assertRaisesRegex(RuntimeError, "rollback"):
                with open_sqlite(path) as conn:
                    conn.execute("INSERT INTO items(value) VALUES (2)")
                    raise RuntimeError("rollback")
            with open_sqlite(path) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
