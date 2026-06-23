import argparse
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import DB_PATH, init_db


CATEGORIES = [
    "Books",
    "Clothing",
    "Electronics",
    "Fitness",
    "Gaming",
    "Home",
    "Kitchen",
    "Outdoors",
    "Stationery",
    "Toys",
]


def product_rows(total):
    random.seed(42)
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for index in range(1, total + 1):
        category = CATEGORIES[index % len(CATEGORIES)]
        created = start + timedelta(seconds=index)
        price_cents = random.randint(299, 199999)
        yield (
            f"{category} Product {index}",
            category,
            price_cents,
            created.isoformat(),
            created.isoformat(),
        )


def seed(total, batch_size, reset):
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        init_db(conn)
        if reset:
            conn.execute("DELETE FROM products")
            conn.commit()

        inserted = 0
        while inserted < total:
            take = min(batch_size, total - inserted)
            first = inserted + 1
            rows = []
            random.seed(42 + inserted)
            start = datetime(2024, 1, 1, tzinfo=timezone.utc)
            for index in range(first, first + take):
                category = CATEGORIES[index % len(CATEGORIES)]
                created = start + timedelta(seconds=index)
                rows.append(
                    (
                        f"{category} Product {index}",
                        category,
                        random.randint(299, 199999),
                        created.isoformat(),
                        created.isoformat(),
                    )
                )

            conn.executemany(
                """
                INSERT INTO products (name, category, price_cents, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
            inserted += take
            print(f"Inserted {inserted:,}/{total:,} products")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Seed the product database quickly.")
    parser.add_argument("--total", type=int, default=200_000)
    parser.add_argument("--batch-size", type=int, default=10_000)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    seed(args.total, args.batch_size, args.reset)


if __name__ == "__main__":
    main()
