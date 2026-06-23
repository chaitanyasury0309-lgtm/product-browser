# CodeVector Product Browser

A small backend for browsing 200,000 products newest first with category filtering and fast pagination.

## Why this approach

- SQLite keeps the project easy to run locally and deploy for a small take-home task.
- Keyset pagination uses `(created_at, id)` instead of `OFFSET`, so page N does not get slower as the user browses deeper.
- The first request returns a snapshot token. Later pages reuse it, so products added after browsing starts do not shift the result set.
- Ordering uses immutable `created_at` plus `id`. Product updates can change `name`, `price`, and `updated_at` without moving rows between pages.

## Run locally

```bash
python seed.py --reset
python app.py
```

Open `http://localhost:8000`.

## API

### `GET /api/products`

Query params:

- `category` optional category name.
- `limit` optional page size from 1 to 200. Default is 50.
- `cursor` token returned by the previous page.
- `snapshot` token returned by the first page.

Example:

```bash
curl "http://localhost:8000/api/products?category=Books&limit=50"
```

### `GET /api/categories`

Returns category counts for the filter dropdown.

### `POST /api/products`

Creates a product.

```bash
curl -X POST "http://localhost:8000/api/products" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"New Product\",\"category\":\"Books\",\"price\":19.99}"
```

### `PATCH /api/products/:id`

Updates a product name or price.

```bash
curl -X PATCH "http://localhost:8000/api/products/1" \
  -H "Content-Type: application/json" \
  -d "{\"price\":29.99}"
```

## Seed data

The seed script inserts in batches with `executemany`, avoiding one slow insert loop with a commit per row.

```bash
python seed.py --total 200000 --batch-size 10000 --reset
```

## Tests

```bash
python -m unittest
```

## Submission note draft

I chose Python's standard library HTTP server with SQLite to keep the implementation small, easy to run, and easy to explain. Pagination is keyset-based over `(created_at, id)` with supporting indexes, which is faster than `OFFSET` for deep pages. The API returns a snapshot token on the first page, and subsequent pages reuse it so newly inserted products do not cause duplicates or skipped rows. Product updates do not reorder the browse list because ordering is based on immutable creation time.

With more time, I would add authentication for write endpoints, move to Postgres for hosted production, add load testing around deeper category pages, and add an OpenAPI spec. I used AI to help scaffold the project, compare pagination approaches, and generate a simple UI, then kept the final implementation intentionally small so I can explain and modify it live.
