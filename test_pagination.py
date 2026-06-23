import os
import sqlite3
import tempfile
import unittest

import app


class PaginationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        self.conn = sqlite3.connect(self.tmp.name)
        self.conn.row_factory = sqlite3.Row
        app.init_db(self.conn)
        rows = [
            ("A", "Books", 1000, "2024-01-01T00:00:01+00:00", "2024-01-01T00:00:01+00:00"),
            ("B", "Books", 1000, "2024-01-01T00:00:02+00:00", "2024-01-01T00:00:02+00:00"),
            ("C", "Books", 1000, "2024-01-01T00:00:03+00:00", "2024-01-01T00:00:03+00:00"),
            ("D", "Books", 1000, "2024-01-01T00:00:04+00:00", "2024-01-01T00:00:04+00:00"),
            ("E", "Books", 1000, "2024-01-01T00:00:05+00:00", "2024-01-01T00:00:05+00:00"),
        ]
        self.conn.executemany(
            """
            INSERT INTO products (name, category, price_cents, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        os.unlink(self.tmp.name)

    def test_keyset_pagination_does_not_duplicate_after_insert(self):
        first = app.list_products(self.conn, category="Books", limit=2)

        self.conn.execute(
            """
            INSERT INTO products (name, category, price_cents, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("New", "Books", 1000, "2024-01-01T00:10:00+00:00", "2024-01-01T00:10:00+00:00"),
        )
        self.conn.commit()

        second = app.list_products(
            self.conn,
            category="Books",
            limit=2,
            cursor=app.decode_token(first["next_cursor"]),
            snapshot=app.decode_token(first["snapshot"]),
        )

        names = [item["name"] for item in first["items"] + second["items"]]
        self.assertEqual(names, ["E", "D", "C", "B"])
        self.assertNotIn("New", names)

    def test_limit_is_clamped(self):
        self.assertEqual(app.parse_limit("999"), app.PAGE_MAX)


if __name__ == "__main__":
    unittest.main()
