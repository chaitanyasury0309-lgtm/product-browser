import base64
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("PRODUCTS_DB", BASE_DIR / "products.db"))
PAGE_DEFAULT = 50
PAGE_MAX = 200
PRODUCT_IMAGES = {
    "Books": [
        "https://images.unsplash.com/photo-1512820790803-83ca734da794",
        "https://images.unsplash.com/photo-1495446815901-a7297e633e8d",
        "https://images.unsplash.com/photo-1524995997946-a1c2e315a42f",
    ],
    "Clothing": [
        "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab",
        "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f",
        "https://images.unsplash.com/photo-1523381210434-271e8be1f52b",
    ],
    "Electronics": [
        "https://images.unsplash.com/photo-1496181133206-80ce9b88a853",
        "https://images.unsplash.com/photo-1516321318423-f06f85e504b3",
        "https://images.unsplash.com/photo-1468495244123-6c6c332eeece",
    ],
    "Fitness": [
        "https://images.unsplash.com/photo-1517836357463-d25dfeac3438",
        "https://images.unsplash.com/photo-1518611012118-696072aa579a",
        "https://images.unsplash.com/photo-1534438327276-14e5300c3a48",
    ],
    "Gaming": [
        "https://images.unsplash.com/photo-1606144042614-b2417e99c4e3",
        "https://images.unsplash.com/photo-1550745165-9bc0b252726f",
        "https://images.unsplash.com/photo-1493711662062-fa541adb3fc8",
    ],
    "Home": [
        "https://images.unsplash.com/photo-1555041469-a586c61ea9bc",
        "https://images.unsplash.com/photo-1484101403633-562f891dc89a",
        "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85",
    ],
    "Kitchen": [
        "https://images.unsplash.com/photo-1556911220-bff31c812dba",
        "https://images.unsplash.com/photo-1556909114-f6e7ad7d3136",
        "https://images.unsplash.com/photo-1556912172-45b7abe8b7e1",
    ],
    "Outdoors": [
        "https://images.unsplash.com/photo-1500534314209-a25ddb2bd429",
        "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee",
        "https://images.unsplash.com/photo-1478131143081-80f7f84ca84d",
    ],
    "Stationery": [
        "https://images.unsplash.com/photo-1455390582262-044cdead277a",
        "https://images.unsplash.com/photo-1517842645767-c639042777db",
        "https://images.unsplash.com/photo-1516321497487-e288fb19713f",
    ],
    "Toys": [
        "https://images.unsplash.com/photo-1566576912321-d58ddd7a6088",
        "https://images.unsplash.com/photo-1558060370-d644479cb6f7",
        "https://images.unsplash.com/photo-1596461404969-9ae70f2830c1",
    ],
}


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_products_created_id
            ON products (created_at DESC, id DESC);

        CREATE INDEX IF NOT EXISTS idx_products_category_created_id
            ON products (category, created_at DESC, id DESC);
        """
    )
    conn.commit()


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def encode_token(value):
    if value is None:
        return None
    raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_token(token):
    if not token:
        return None
    try:
        padded = token + ("=" * (-len(token) % 4))
        return json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except (ValueError, json.JSONDecodeError):
        raise ValueError("Invalid pagination token")


def parse_limit(raw_limit):
    if not raw_limit:
        return PAGE_DEFAULT
    try:
        return max(1, min(PAGE_MAX, int(raw_limit)))
    except ValueError:
        raise ValueError("limit must be a number")


def row_to_product(row):
    image_url = product_image_url(row["category"], row["id"])
    return {
        "id": row["id"],
        "name": row["name"],
        "category": row["category"],
        "price": round(row["price_cents"] / 100, 2),
        "image_url": image_url,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def product_image_url(category, product_id):
    images = PRODUCT_IMAGES.get(category) or PRODUCT_IMAGES["Books"]
    base_url = images[product_id % len(images)]
    return f"{base_url}?auto=format&fit=crop&w=240&h=180&q=80"


def get_snapshot(conn, category=None):
    params = []
    where = ""
    if category:
        where = "WHERE category = ?"
        params.append(category)

    row = conn.execute(
        f"""
        SELECT created_at, id
        FROM products
        {where}
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        params,
    ).fetchone()
    if not row:
        return None
    return {"created_at": row["created_at"], "id": row["id"]}


def list_products(conn, category=None, limit=PAGE_DEFAULT, cursor=None, snapshot=None):
    snapshot = snapshot or get_snapshot(conn, category)
    if snapshot is None:
        return {"items": [], "next_cursor": None, "snapshot": None, "limit": limit}

    params = [snapshot["created_at"], snapshot["created_at"], snapshot["id"]]
    filters = ["(created_at < ? OR (created_at = ? AND id <= ?))"]

    if category:
        filters.insert(0, "category = ?")
        params.insert(0, category)

    if cursor:
        filters.append("(created_at < ? OR (created_at = ? AND id < ?))")
        params.extend([cursor["created_at"], cursor["created_at"], cursor["id"]])

    params.append(limit + 1)
    rows = conn.execute(
        f"""
        SELECT id, name, category, price_cents, created_at, updated_at
        FROM products
        WHERE {" AND ".join(filters)}
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()

    page_rows = rows[:limit]
    next_cursor = None
    if len(rows) > limit and page_rows:
        last = page_rows[-1]
        next_cursor = encode_token({"created_at": last["created_at"], "id": last["id"]})

    return {
        "items": [row_to_product(row) for row in page_rows],
        "next_cursor": next_cursor,
        "snapshot": encode_token(snapshot),
        "limit": limit,
    }


def categories(conn):
    rows = conn.execute(
        """
        SELECT category, COUNT(*) AS count
        FROM products
        GROUP BY category
        ORDER BY category
        """
    ).fetchall()
    return [{"category": row["category"], "count": row["count"]} for row in rows]


def create_product(conn, payload):
    name = str(payload.get("name", "")).strip()
    category = str(payload.get("category", "")).strip()
    price = payload.get("price")
    if not name or not category or price is None:
        raise ValueError("name, category, and price are required")

    created_at = now_iso()
    price_cents = int(round(float(price) * 100))
    cur = conn.execute(
        """
        INSERT INTO products (name, category, price_cents, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (name, category, price_cents, created_at, created_at),
    )
    conn.commit()
    return conn.execute("SELECT * FROM products WHERE id = ?", (cur.lastrowid,)).fetchone()


def update_product(conn, product_id, payload):
    allowed = {}
    if "name" in payload:
        allowed["name"] = str(payload["name"]).strip()
    if "price" in payload:
        allowed["price_cents"] = int(round(float(payload["price"]) * 100))
    if not allowed:
        raise ValueError("name or price is required")

    allowed["updated_at"] = now_iso()
    assignments = ", ".join(f"{key} = ?" for key in allowed)
    values = list(allowed.values()) + [product_id]
    cur = conn.execute(f"UPDATE products SET {assignments} WHERE id = ?", values)
    conn.commit()
    if cur.rowcount == 0:
        return None
    return conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()


class ProductHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        try:
            if parsed.path == "/":
                self.send_static("index.html", "text/html; charset=utf-8")
            elif parsed.path == "/styles.css":
                self.send_static("styles.css", "text/css; charset=utf-8")
            elif parsed.path == "/app.js":
                self.send_static("app.js", "application/javascript; charset=utf-8")
            elif parsed.path == "/api/health":
                self.send_json({"ok": True})
            elif parsed.path == "/api/categories":
                with get_connection() as conn:
                    self.send_json({"items": categories(conn)})
            elif parsed.path == "/api/products":
                self.handle_list_products(params)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except sqlite3.Error as exc:
            self.send_json({"error": f"database error: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self):
        if self.path != "/api/products":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self.read_json()
            with get_connection() as conn:
                product = create_product(conn, payload)
            self.send_json(row_to_product(product), HTTPStatus.CREATED)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_PATCH(self):
        match = re.fullmatch(r"/api/products/(\d+)", self.path)
        if not match:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self.read_json()
            with get_connection() as conn:
                product = update_product(conn, int(match.group(1)), payload)
            if product is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self.send_json(row_to_product(product))
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def handle_list_products(self, params):
        category = params.get("category", [None])[0] or None
        limit = parse_limit(params.get("limit", [None])[0])
        cursor = decode_token(params.get("cursor", [None])[0])
        snapshot = decode_token(params.get("snapshot", [None])[0])

        with get_connection() as conn:
            result = list_products(conn, category, limit, cursor, snapshot)
        self.send_json(result)

    def send_static(self, filename, content_type):
        path = BASE_DIR / "public" / filename
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


def main():
    with get_connection() as conn:
        init_db(conn)

    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), ProductHandler)
    print(f"Product browser running on http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
