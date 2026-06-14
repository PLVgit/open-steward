# Open Steward

> Local-first pipeline intelligence for Analytics Engineers.

Open Steward scans SQL-config-driven ETL pipelines, reconstructs their dependencies, detects risky transformations, and validates data quality — from a simple CSV config plus your table data (CSV or Parquet).

---

## Quick start

```bash
cd backend
pip install -e ".[dev]"
open-steward list --file demo_data/demo_config.csv
```

> **Windows / PATH note:** If `open-steward` is not found after install, either add the Python scripts directory to your PATH or invoke the tool as `python -m app.cli` from the `backend/` directory.

---

## Demo walkthrough

The `demo_data/` directory contains a small e-commerce pipeline config and local table snapshots. Each step below shows the exact command and its output.

### Pipeline: what's configured

The demo models a four-job pipeline:

| Job | Source | Target | Status |
|-----|--------|--------|--------|
| `etl_001` — Load Orders | `raw.orders` | `staging.orders` | enabled |
| `etl_002` — Load Customers | `raw.customers` | `staging.customers` | enabled |
| `etl_003` — Enrich Orders | `staging.orders` | `mart.orders_enriched` | enabled |
| `etl_004` — Daily Revenue | `mart.orders_enriched` | `mart.daily_revenue` | **disabled** |

---

### 1. List all ETL jobs

```bash
open-steward list --file demo_data/demo_config.csv
```

```
Open Steward  ·  demo_config.csv  ·  4 jobs (3 enabled)

KEY      NAME            ENABLED  SOURCE                TARGET                LOAD
etl_001  Load Orders     yes      raw.orders            staging.orders        full
etl_002  Load Customers  yes      raw.customers         staging.customers     full
etl_003  Enrich Orders   yes      staging.orders        mart.orders_enriched  full
etl_004  Daily Revenue   no       mart.orders_enriched  mart.daily_revenue    incremental
```

---

### 2. Show the dependency graph and execution order

```bash
open-steward graph --file demo_data/demo_config.csv
```

```
Open Steward  ·  demo_config.csv  ·  execution order

  1   raw.orders
  2   raw.customers
  3   staging.orders
  4   staging.customers
  5   mart.orders_enriched
  6   mart.daily_revenue

No cycles detected.  ✓
```

> **Note:** The graph command includes **all jobs** — both enabled and disabled. Disabled jobs are not hidden from the dependency graph because downstream jobs may still depend on their output tables, and the full graph is needed to detect missing or broken dependencies. Use `open-steward list` to see which jobs are enabled or disabled.

---

### 3. Check for structural and SQL issues (no data required)

```bash
open-steward check --file demo_data/demo_config.csv
```

```
Open Steward  ·  demo_config.csv

No errors.

WARNINGS (2)

  [select_star]  etl_001
  Job 'etl_001' uses SELECT *, which may expose unexpected columns to downstream consumers.
  → Replace SELECT * with an explicit column list.

  [explicit_cast]  etl_002
  Job 'etl_002' contains a CAST or TRY_CAST expression that may silently change data types.
  → Verify that the cast is intentional and that downstream consumers expect the converted type.

INFO (2)

  [missing_filter_on_full_load]  etl_001
  Job 'etl_001' is a full load with no WHERE or LIMIT clause. It will replace the entire target table on every run.
  → Confirm this full replacement is intentional, or add a WHERE/LIMIT clause to scope the load.

  [missing_filter_on_full_load]  etl_002
  Job 'etl_002' is a full load with no WHERE or LIMIT clause. It will replace the entire target table on every run.
  → Confirm this full replacement is intentional, or add a WHERE/LIMIT clause to scope the load.

────────────────────────────────────────────────
0 errors · 2 warnings · 2 info
```

Exits with code `0` — no errors found. Exit code `1` means at least one error finding.

`etl_003` is not flagged because its SQL contains a `WHERE` clause. `etl_004` is not flagged because its `load_type` is `incremental`.

---

### 4. Check with local data snapshots (adds reconciliation)

The `--data-dir` flag points Open Steward at local CSV or Parquet snapshots of source and target tables. These are compared to detect row loss, duplicate primary keys, and null primary keys.

```bash
open-steward check --file demo_data/demo_config.csv --data-dir demo_data
```

```
Open Steward  ·  demo_config.csv

ERRORS (1)

  [duplicate_primary_key]  staging.customers
  Primary key 'customer_id' is not unique in target table 'staging.customers': duplicate_key_count=1, target_count=11.
  → Investigate the ETL logic that writes to 'staging.customers'. Deduplicate on 'customer_id' before loading, or add a DISTINCT clause.

WARNINGS (3)

  [select_star]  etl_001
  Job 'etl_001' uses SELECT *, which may expose unexpected columns to downstream consumers.
  → Replace SELECT * with an explicit column list.

  [explicit_cast]  etl_002
  Job 'etl_002' contains a CAST or TRY_CAST expression that may silently change data types.
  → Verify that the cast is intentional and that downstream consumers expect the converted type.

  [row_count_drop]  staging.orders
  Full-load target has fewer rows than source: source_count=20, target_count=18, lost_rows=2, loss_pct=10.0%.
  → Check the ETL transformation for unintended filtering or data loss. Consider adding row count assertions to the pipeline.

INFO (2)

  [missing_filter_on_full_load]  etl_001
  Job 'etl_001' is a full load with no WHERE or LIMIT clause. It will replace the entire target table on every run.
  → Confirm this full replacement is intentional, or add a WHERE/LIMIT clause to scope the load.

  [missing_filter_on_full_load]  etl_002
  Job 'etl_002' is a full load with no WHERE or LIMIT clause. It will replace the entire target table on every run.
  → Confirm this full replacement is intentional, or add a WHERE/LIMIT clause to scope the load.

────────────────────────────────────────────────
1 errors · 3 warnings · 2 info
```

Exits with code `1` — one error finding (`duplicate_primary_key`).

`etl_003` and `etl_004` are silently skipped: `etl_003`'s target file does not exist locally, and `etl_004` is disabled. Missing local snapshots are never treated as errors — reconciliation is opt-in.

---

### 5. Profile a table for data quality issues

```bash
open-steward profile --table staging.orders --data-dir demo_data
```

```
Open Steward  ·  staging.orders  ·  profile

18 rows · 5 columns

COLUMN       DTYPE    NULLS    EMPTY    DISTINCT
order_id     BIGINT   0.0%     —        100.0%
customer_id  BIGINT   0.0%     —        55.6%
amount       DOUBLE   0.0%     —        94.4%
status       VARCHAR  0.0%     0.0%     16.7%
coupon_code  VARCHAR  83.3%    0.0%     16.7%

────────────────────────────────────────────────
WARNINGS (1)

  [high_null_rate]  staging.orders
  Column 'coupon_code' in 'staging.orders' has 83.3% null values (threshold: 20.0%).
  → Investigate whether null values in 'coupon_code' are expected.

────────────────────────────────────────────────
0 errors · 1 warnings · 0 info
```

`—` means the metric is not applicable (empty string rate is only tracked for VARCHAR columns).

---

### 6. Show per-job ETL statistics

`stats` reports the numeric facts of each enabled job's source/target snapshots — the data behind reconciliation, without the judgments. It complements `check`: `check` says *what is wrong*, `stats` says *what happened numerically*.

```bash
open-steward stats --file demo_data/demo_config.csv --data-dir demo_data
```

```
Open Steward  ·  demo_config.csv  ·  3 enabled jobs

KEY      TARGET                SOURCE   TARGET#  LOST    LOSS%    PK NULLS  PK DUPS
etl_001  staging.orders        20       18       2       10.0%    0         0
etl_002  staging.customers     10       11       0       0.0%     0         1
etl_003  mart.orders_enriched  18       —        —       —        —         —

Statistics describe what happened numerically; run 'check' for findings.
```

`—` means the value is not computable — here `mart.orders_enriched` has no local snapshot, so its target-side metrics are unknown. It does **not** mean zero. Disabled jobs (`etl_004`) are excluded.

---

## Understanding findings

### Structural findings

| Finding | Severity | What it means |
|---------|----------|---------------|
| `circular_dependency` | error | ETL jobs form a loop — no valid execution order exists |
| `duplicate_target` | error | Two or more jobs write to the same target table |
| `disabled_dependency` | error | An enabled job depends on output produced only by a disabled job |
| `unresolved_upstream` | info | A source table is not produced by any job and does not match a known external prefix (`raw.`, `source.`, `landing.`, `external.`) |

### SQL findings

Detected by parsing the `sql_query` field of each job using [sqlglot](https://github.com/tobymao/sqlglot). Jobs with no `sql_query` are silently skipped.

| Finding | Severity | What it means |
|---------|----------|---------------|
| `select_star` | warning | Query uses `SELECT *` — exposes unexpected columns if the source schema changes |
| `explicit_cast` | warning | Query uses `CAST()` or `TRY_CAST()` — may silently change types for downstream consumers |
| `cross_join` | error | Query contains an explicit `CROSS JOIN` — likely produces a cartesian product |
| `missing_filter_on_full_load` | info | Full-load job has no `WHERE` or `LIMIT` clause — will replace the entire target table on every run |
| `unparseable_sql` | warning | SQL could not be parsed — query syntax may be dialect-specific or malformed |

### Reconciliation findings

Require local table snapshots (CSV or Parquet). Only enabled jobs are reconciled. Jobs where either the source or target file is absent are silently skipped.

| Finding | Severity | What it means |
|---------|----------|---------------|
| `empty_target` | warning | Target table has 0 rows while source has rows |
| `row_count_drop` | warning | Full-load target has fewer rows than source, and the loss is **not** explained by a simple filter — includes `source_count`, `target_count`, `lost_rows`, `loss_pct` |
| `row_loss_explained_by_filter` | info | Full-load row drop is fully accounted for by the job's simple `WHERE` filter — includes `source_count`, `expected_after_filter_count`, `target_count`, `filtered_out_rows`, `filtered_out_pct` |
| `unexpected_row_loss` | warning | Full-load target has fewer rows than the job's simple `WHERE` filter would yield — includes the filter metrics plus `unexpected_loss_rows`, `unexpected_loss_pct` |
| `null_primary_key` | error | Primary key column contains null values in the target — includes `null_count`, `null_pct` |
| `duplicate_primary_key` | error | Primary key is not unique in the target — includes `duplicate_key_count` |

**Filter-aware reconciliation.** For a full-load job whose SQL is a *simple single-source `WHERE` filter*, Open Steward counts how many source rows pass the filter (`expected_after_filter_count`) and compares it to the target row count: an exact match yields the `row_loss_explained_by_filter` info finding (no false-positive `row_count_drop`), while a target below the expected count yields `unexpected_row_loss`. Anything not provably simple — multiple source tables, CTEs, subqueries, `UNION`, `GROUP BY`/`HAVING`/`DISTINCT`/`LIMIT`, aggregate/window functions, or non-trivial `WHERE` expressions — falls back to plain `row_count_drop`.

### Join-aware advisory statistics

For a full-load job whose SQL is a *simple two-table `INNER`/`LEFT` join* with a single equality `ON` (and an optional left-only `WHERE`), Open Steward explains the row count as a staged chain — all computed as **scalar aggregate counts; the join result is never materialized**:

```
source_count → after_filter_count → expected_after_join_count → target_count
```

| Finding | Severity | What it means |
|---------|----------|---------------|
| `row_count_change_explained_by_transformations` | info | `target_count` equals `expected_after_join_count` — the change is fully explained by the filter and join |
| `unexpected_row_loss_after_join` | warning | Target has fewer rows than the filter+join explain — includes `unexpected_loss_rows` |
| `unexpected_row_surplus_after_join` | warning | Target has more rows than the filter+join explain — includes `unexpected_surplus_rows` |
| `join_unmatched_rows` | warning (INNER) / info (LEFT) | Some left rows have no matching right key (dropped by INNER, kept with NULLs by LEFT) — includes `join_match_rate` |
| `join_key_nulls` | info | A join key contains nulls, which never match |
| `possible_row_multiplication` | warning | The right join key is not unique, so matched left rows can fan out |
| `possible_many_to_many_join` | warning | Both join keys have duplicate values — a many-to-many join can multiply rows |

These are **advisory** — they describe structural row-count risks and never assert the result is wrong. Anything outside the supported shape (more than one join; `RIGHT`/`FULL`/`CROSS`/`NATURAL`/`USING`; composite or non-equality `ON`; ambiguous unqualified keys; a `WHERE` referencing the right table; CTEs/subqueries/aggregates/etc.) falls back safely with no join findings.

### Profiling findings

Generated per column by `open-steward profile`. Thresholds are fixed defaults in the current release.

| Finding | Severity | Threshold | What it means |
|---------|----------|-----------|---------------|
| `all_nulls` | error | 100% null | Column is entirely null |
| `high_null_rate` | warning | ≥ 20% null | Column has a high proportion of null values |
| `constant_column` | info | 1 distinct value, row count > 1 | Column has only one unique value — may be a fixed category or a loading bug |
| `high_empty_string_rate` | warning | ≥ 10% empty strings | VARCHAR column has many empty string values (distinct from null) |

---

## CLI reference

```
open-steward [COMMAND] [OPTIONS]
```

| Command | Required options | Optional options | Description |
|---------|-----------------|-----------------|-------------|
| `list` | `--file PATH` | — | List all ETL jobs in the config |
| `graph` | `--file PATH` | — | Show dependency graph and execution order |
| `check` | `--file PATH` | `--data-dir PATH` | Run all structural, SQL and reconciliation checks |
| `profile` | `--table NAME` `--data-dir PATH` | — | Profile a table for data quality issues |
| `stats` | `--file PATH` `--data-dir PATH` | — | Show per-job ETL statistics (row counts, loss, primary-key metrics) |

`check` and `profile` exit `1` when any `error`-severity finding is detected (else `0`), and `graph` exits `1` when a cycle is detected — suitable for CI pipelines. `list` and `stats` are informational and always exit `0`.

---

## API reference

Start the API server:

```bash
cd backend
uvicorn app.main:app --reload
```

Interactive docs: `http://localhost:8000/docs`

Config-driven endpoints accept `?file=<filename>`, where the file must be located inside `backend/samples/`. Data-driven endpoints also accept `?data_dir=<subdir>`, confined to `backend/demo_data/` (defaults to `.`). `/profile/` takes `?table=<schema.table>` instead of a config file. These path restrictions keep the HTTP surface safe; the CLI accepts arbitrary local paths.

| Method | Path | Query | Description |
|--------|------|-------|-------------|
| GET | `/pipelines/` | `file` | List all jobs |
| GET | `/pipelines/{config_key}` | `file` | Get one job by key |
| GET | `/graph/` | `file` | Dependency graph and execution order |
| GET | `/findings/` | `file`, `data_dir` *(optional)* | Structural + SQL findings; reconciliation findings too when `data_dir` is given |
| GET | `/statistics/` | `file`, `data_dir` | Per-job ETL statistics |
| GET | `/profile/` | `table`, `data_dir` | Table profile + data-quality findings |

> Without `data_dir`, `/findings/` returns structural + SQL findings only (unchanged). Supplying `data_dir` adds reconciliation findings (row loss, duplicate/null primary keys), mirroring the CLI `check --data-dir`. Reconciliation requires local table snapshots under the data directory.

Examples:

```bash
curl "http://localhost:8000/findings/?file=sample_config.csv"
curl "http://localhost:8000/findings/?file=demo_config.csv&data_dir=."   # + reconciliation findings
curl "http://localhost:8000/statistics/?file=demo_config.csv&data_dir=."
curl "http://localhost:8000/profile/?table=staging.orders&data_dir=."
```

---

## Project structure

```
backend/
  app/
    adapters/
      base.py                    # PipelineSource protocol
      csv_adapter.py             # reads ETL config CSVs
      data_source.py             # DataSource protocol
      local_file_data_source.py  # DuckDB-backed local file reader
    api/
      routes/
        findings.py
        graph.py
        pipelines.py
        statistics.py            # /statistics endpoint
        profile.py               # /profile endpoint
      deps.py                    # shared FastAPI dependencies (path safety)
    models/
      column_info.py
      finding.py
      job_statistics.py          # per-job ETL statistics model
      pipeline_job.py
      table_profile.py
    schemas/
      graph_schema.py
      profile_schema.py          # /profile response (profile + findings)
    services/
      dq_profiler.py             # per-column data quality profiling
      etl_statistics.py          # per-job ETL statistics
      finding_detector.py        # structural findings
      graph_builder.py           # NetworkX dependency graph
      reconciliation_engine.py   # source vs target reconciliation
      sql_analyzer.py            # sqlglot SQL pattern detection
    tests/
    cli.py                       # typer CLI
    main.py                      # FastAPI application
  demo_data/                     # demo pipeline config and table snapshots
    demo_config.csv
    raw/
    staging/
  samples/                       # sample configs for API and tests
  pyproject.toml
  README.md

# A separate React + TypeScript UI lives in ../frontend (see frontend/README.md).
```

---

## Running tests

```bash
cd backend
python -m pytest -v
```

---

## Current analysis scope

Analysis is deliberately conservative — Open Steward explains what it can prove and falls back safely otherwise.

- **One source table per job.** `PipelineJob.source_table` is a single string. Jobs that join multiple tables are modelled through the job's SQL (see join-aware reconciliation), with the raw SQL preserved for analysis.
- **Reconciliation reads table data** from CSV or Parquet under `--data-dir`.
- **Single-column primary keys.** Composite primary keys (e.g. `order_id, line_id`) are not yet covered in reconciliation or profiling.
- **Simple SQL shapes for transformation explanation** — a single `SELECT`, one two-table INNER/LEFT join, a single equality `ON`, and a simple left-side `WHERE`. More complex SQL falls back to plain row-count reconciliation.
- **Column name restrictions.** Columns with spaces or special characters (e.g. `Order Date`) are skipped in profiling. Column names must match `[A-Za-z0-9_]+`.

---

## Roadmap

**Shipped**
- React + TypeScript UI with an interactive pipeline graph (React Flow), findings dashboard, ETL statistics panel and table profile page.
- ETL-level statistics, exposed via the `stats` CLI command and the `/statistics/` endpoint.
- Filter-aware reconciliation: full-load row drops explained by a simple `WHERE` filter are reported as expected (`row_loss_explained_by_filter`) instead of false-positive `row_count_drop`; shortfalls below the filtered count are flagged as `unexpected_row_loss`.
- Join-aware advisory statistics: simple two-table INNER/LEFT joins are explained as a staged `source → after_filter → expected_after_join → target` chain, with advisory findings for unmatched rows, null keys and possible row multiplication / many-to-many fan-out.

**Later** (not started)
- More transformation shapes: RIGHT/FULL/NATURAL joins, composite join keys, multiple joins, post-join WHERE.
- Additional data-source integrations and adapters.
- Row-loss tolerance thresholds per job (`row_loss_tolerance_pct`).
- Distribution and histogram profiling (e.g. via Polars).
- `--output json` flag on all CLI commands; suggested data-quality rules from profile results.
