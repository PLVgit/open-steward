# Open Steward — Showcase Walkthrough

A reproducible, synthetic showcase demo designed to exercise **all** of Open
Steward's analysis capabilities — structural checks, SQL risk analysis,
source↔target reconciliation, filter-aware and join-aware transformation
reconciliation, and data-quality profiling — through the CLI, the API, and the UI.

The data is entirely synthetic (fake orders/customers/products), uses dedicated
`showcase_*` table namespaces so it stands on its own, and is small (≈4–12 rows
per source table) but deliberately constructed so every row-count causality is
predictable — which makes it ideal for a guided demo or a portfolio screenshot.

> It runs through the same engine, CLI, API, and UI as everything else — there is
> no separate product mode. Follow it top to bottom for a complete tour.

---

## What's in the showcase

**Config** (in `backend/samples/`, selectable by the API and UI):

- `showcase_config.csv` — 11 jobs.

**Source tables** (`backend/demo_data/showcase_raw/`):

- `orders.csv` — 12 rows. Columns: `order_id, customer_id, product_id, status, amount, coupon_code, notes, source_system`. Statuses: 6 `completed`, 3 `paid`, 1 `cancelled`, 2 `pending`. Customer IDs `C1–C5` match `customers_clean`; `C9` (×2) does not; one blank (NULL) `customer_id`. Product IDs `P1–P3` exist in `promotions`; `P4`/`P5` do not.
- `customers_clean.csv` — 5 rows, unique `customer_id`.
- `products.csv` — 4 rows, unique `product_id` (`P1–P4`).
- `promotions.csv` — 4 rows, `product_id` **`P1` duplicated** (fan-out source).

**Staging targets** (`backend/demo_data/showcase_staging/`):

- `orders_loaded.csv` — 10 rows. The kitchen-sink quality table (duplicate + null PK, high null, high empty-string, constant, all-null columns).
- `completed_orders.csv` — 6 rows (exactly the `completed` orders).
- `paid_orders_broken.csv` — 2 rows (one fewer than the filter predicts).

**Mart targets** (`backend/demo_data/showcase_mart/`):

- `orders_customers_inner.csv` — 9 rows (matches the INNER join output exactly).
- `orders_customer_surplus.csv` — 11 rows (2 more than expected).
- `orders_customers_loss.csv` — 7 rows (2 fewer than expected).
- `orders_promos_left.csv` — 16 rows (matches the LEFT fan-out output exactly).
- `products_promos_left.csv` — 5 rows (matches the LEFT output exactly).

(The `sc_cast_demo`, `sc_cross_demo`, and `sc_unparseable_demo` jobs have **no
target snapshot on purpose**, so reconciliation skips them and they contribute
only SQL findings.)

---

## How to run

### Optional — verify your setup

```bash
cd backend
python -m pytest -q        # 242 passed
```

### CLI checks (run from `backend/`)

```bash
open-steward list    --file samples/showcase_config.csv
open-steward graph   --file samples/showcase_config.csv
open-steward check   --file samples/showcase_config.csv
open-steward check   --file samples/showcase_config.csv --data-dir demo_data
open-steward stats   --file samples/showcase_config.csv --data-dir demo_data
open-steward profile --table showcase_staging.orders_loaded --data-dir demo_data
```

> If the `open-steward` CLI isn't on PATH, run it as a module from `backend/`:
> `python -m app.cli …` (or `py -m app.cli …` on Windows).

### Backend server + API

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

```bash
curl "http://localhost:8000/findings/?file=showcase_config.csv&data_dir=."
curl "http://localhost:8000/statistics/?file=showcase_config.csv&data_dir=."
curl "http://localhost:8000/profile/?table=showcase_staging.orders_loaded&data_dir=."
curl "http://localhost:8000/graph/?file=showcase_config.csv"
```

(`file` resolves under `backend/samples/`; `data_dir=.` resolves under
`backend/demo_data/`.)

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

In the header **Config** input, replace `demo_config.csv` with
**`showcase_config.csv`** (the selector is a free-text field — no UI change was
needed). Every page then reflects the showcase.

---

## Which UI pages to inspect

- **Overview** — confirms the backend connection and lists all 11 showcase jobs.
- **Graph** — the dependency graph: `showcase_raw.orders` and
  `showcase_raw.products` fan out to the staging/mart targets; no cycles.
- **Findings** — the full catalog below (the dashboard requests with
  `data_dir=.`, so reconciliation + join findings appear alongside structural/SQL).
- **Statistics** — per-job row counts; note the `—` for the three SQL-risk-only
  jobs whose targets have no snapshot.
- **Profile** — type `showcase_staging.orders_loaded` to see the data-quality
  findings.

### Graph

`showcase_raw.orders` and `showcase_raw.products` fan out left→right into the
staging and mart lanes. Edge labels are hidden by default; hover or click to
reveal them.

![Showcase dependency graph in source, staging and mart lanes](screenshots/graph-showcase.png)

Click an edge to inspect a single dependency (config key, source, target), or a
table to inspect its namespace and dependency counts:

| Edge inspector | Table inspector |
|---|---|
| ![Selected dependency edge showing its config key, source and target](screenshots/graph-inspector-edge-showcase.png) | ![Selected table showing its namespace and dependency counts](screenshots/graph-inspector-node-showcase.png) |

### Findings

With `showcase_config.csv` and reconciliation enabled, the transformation-aware
findings appear alongside structural and SQL findings:

![Findings showing transformation-aware reconciliation results](screenshots/findings-transformations-showcase.png)

Filter to **Errors** to isolate `cross_join`, `null_primary_key`, and
`duplicate_primary_key`:

![Findings filtered to error-severity issues](screenshots/findings-errors-showcase.png)

### Statistics

Per-job row counts and primary-key metrics; the three SQL-risk-only jobs without a
target snapshot show `—`:

![Per-job ETL statistics for the showcase config](screenshots/statistics-showcase.png)

### Profile

`showcase_staging.orders_loaded` surfaces the kitchen-sink data-quality findings:

![Profile of showcase_staging.orders_loaded with data-quality findings](screenshots/profile-showcase.png)

---

## Expected findings and why

### `check --file samples/showcase_config.csv` (structural + SQL only)
Exit code **1** (a `cross_join` error). Produces:

- `cross_join` (error) — `sc_cross_demo`.
- `select_star` (warning) — `sc_load_orders`, `sc_cross_demo`.
- `explicit_cast` (warning) — `sc_cast_demo`.
- `unparseable_sql` (warning) — `sc_unparseable_demo`.
- `unresolved_upstream` (info) — `showcase_raw.orders`, `showcase_raw.products`
  (raw sources not produced by any job; `showcase_raw.` is not a recognized
  external prefix).
- `missing_filter_on_full_load` (info) — every full-load job with no `WHERE`
  (the load, all join jobs, and the cast/cross demos).

### `check … --data-dir demo_data` (adds reconciliation + transformation analysis)
Exit code **1**. Adds, on top of the above:

| Job → target | Finding(s) | Why |
|---|---|---|
| `sc_load_orders` → `orders_loaded` | `row_count_drop` (warning), `null_primary_key` (error), `duplicate_primary_key` (error) | 12 → 10 rows; `order_id` has 1 null and 1 duplicate |
| `sc_completed_orders` → `completed_orders` | `row_loss_explained_by_filter` (info) | `WHERE status='completed'` ⇒ expected 6, target 6 |
| `sc_paid_orders` → `paid_orders_broken` | `unexpected_row_loss` (warning) | `WHERE status='paid'` ⇒ expected 3, target 2 (loss 1) |
| `sc_orders_customers_inner` | `row_count_change_explained_by_transformations` (info), `join_unmatched_rows` (warning), `join_key_nulls` (info) | INNER ⇒ expected 9, target 9; 3 unmatched left rows; 1 null join key |
| `sc_orders_customer_surplus` | `unexpected_row_surplus_after_join` (warning) + unmatched/nulls advisories | INNER ⇒ expected 9, target 11 (surplus 2) |
| `sc_orders_customers_loss` | `unexpected_row_loss_after_join` (warning) + unmatched/nulls advisories | INNER ⇒ expected 9, target 7 (loss 2) |
| `sc_orders_promos_left` | `row_count_change_explained_by_transformations` (info), `possible_many_to_many_join` (warning), `join_unmatched_rows` (info) | LEFT fan-out ⇒ expected 16, target 16; both keys duplicated; 2 unmatched (P4/P5) kept |
| `sc_products_promos_left` | `row_count_change_explained_by_transformations` (info), `possible_row_multiplication` (warning), `join_unmatched_rows` (info) | LEFT ⇒ expected 5, target 5; right key `P1` duplicated, left unique; 1 unmatched (P4) |

### `profile --table showcase_staging.orders_loaded`
Exit code **1**. Produces:

- `all_nulls` (error) — `legacy_flag` is entirely null.
- `high_null_rate` (warning) — `coupon_code` 80% null.
- `high_empty_string_rate` (warning) — `notes` 60% empty strings.
- `constant_column` (info) — `region` has a single distinct value.
- Plus useful distinct counts (e.g. `order_id` 80% distinct, `status` 40%).

---

## Staged transformation chains (the key demonstration)

`source_count → after_filter_count → expected_after_join_count → target_count`

| Job | source | after_filter | expected_after_join | target | Result |
|---|---|---|---|---|---|
| `sc_load_orders` | 12 | 12 | — (no join) | 10 | `row_count_drop` (unexplained −2) |
| `sc_completed_orders` | 12 | **6** | — | 6 | explained by filter |
| `sc_paid_orders` | 12 | **3** | — | 2 | `unexpected_row_loss` (−1) |
| `sc_orders_customers_inner` | 12 | 12 | **9** | 9 | explained (INNER drops 3 unmatched) |
| `sc_orders_customer_surplus` | 12 | 12 | **9** | 11 | `unexpected_row_surplus_after_join` (+2) |
| `sc_orders_customers_loss` | 12 | 12 | **9** | 7 | `unexpected_row_loss_after_join` (−2) |
| `sc_orders_promos_left` | 12 | 12 | **16** | 16 | explained (LEFT fan-out +4) |
| `sc_products_promos_left` | 4 | 4 | **5** | 5 | explained (LEFT fan-out +1) |

---

## Showcase screenshots

These are captured against `showcase_config.csv` and live under
`docs/screenshots/` (used throughout this guide and the root README):

| File | Page / view |
|---|---|
| `overview-showcase.png` | Overview — connection status + job roster |
| `graph-showcase.png` | Graph — source → staging → mart lanes |
| `graph-inspector-edge-showcase.png` | Graph — selected-edge inspector |
| `graph-inspector-node-showcase.png` | Graph — selected-table inspector |
| `findings-transformations-showcase.png` | Findings — transformation-aware results |
| `findings-errors-showcase.png` | Findings — filtered to error severity |
| `statistics-showcase.png` | Statistics — per-job ETL telemetry |
| `profile-showcase.png` | Profile — `showcase_staging.orders_loaded` |
