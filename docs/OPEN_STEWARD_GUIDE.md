# Open Steward — Local-first Pipeline Intelligence & Data Quality Platform

Open Steward is a local-first tool that reads ETL pipeline definitions — from a
config CSV or a dbt manifest — reconstructs the dependencies between jobs and
tables, flags risky SQL, explains row-count changes between source and target
data, and profiles final tables for data-quality issues. Point it at your
pipeline definitions and table data (CSV/Parquet snapshots, a DuckDB database,
or Postgres) and run it through a CLI, a FastAPI service, or a React UI.

---

## 1. Problem it solves

SQL-config-driven ETL pipelines (a metadata table or CSV of jobs, each with a
`source_table`, `target_table`, and a `sql_query`) are common, but they become
hard to reason about as they grow:

- **What runs, and in what order?** Dependencies are implicit in the source/target
  tables, not written down.
- **Which transformations are risky?** `SELECT *`, casts, cross joins, and
  unfiltered full loads are easy to miss in a long config.
- **Did the data survive the pipeline?** A job may silently drop rows, duplicate
  primary keys, or multiply rows through a join — and nobody notices until a
  downstream number looks wrong.
- **Is the final table clean?** High null rates, empty strings, and constant
  columns hide in the output.

Open Steward helps an Analytics Engineer **inspect and explain** these issues
before they reach downstream consumers, with a fast local setup — just a Python
and Node toolchain.

---

## 2. What Open Steward does today

All of the following are implemented and covered by tests (366 backend tests,
66 frontend tests):

- **Graph table hiding** — jobs tagged `hide_from_graph` (a dbt model tag, or a
  value in the optional CSV `tags` column) hide their target table from the UI
  graph, with a one-click "Show hidden" toggle. Tags never affect findings,
  reconciliation or statistics.
- **Tunable strictness** — row-loss tolerance for reconciliation and null/empty
  profiling thresholds, as CLI flags and API params (defaults unchanged).
- **Single-pass profiling** — one table scan computes every column's counts,
  instead of three queries per column.

- **CSV-driven pipeline config ingestion** — parse a config CSV into typed
  `PipelineJob` objects.
- **dbt manifest ingestion** — parse a dbt `manifest.json` (compiled preferred):
  models become jobs with multi-parent lineage (`depends_on`), compiled SQL,
  materialization-derived load types, and **primary keys derived from dbt's own
  `unique` tests**. Ephemeral models are resolved through to their parents.
- **Database connectivity** — reconcile and profile directly against a DuckDB
  database file, or Postgres attached read-only via DuckDB's postgres
  extension. Credentials live in environment variables (`${VAR}` placeholders
  in the URL are expanded, never logged) and URLs are CLI-only — the HTTP API
  never accepts them.
- **Pipeline dependency graph** — build a table-level dependency graph (NetworkX)
  from each job's source/target tables.
- **Execution order calculation** — topological order, with cycle detection.
- **Structural findings** — circular dependencies, duplicate targets,
  enabled-depends-on-disabled, and unresolved upstreams.
- **SQL risk analysis** (sqlglot) — `SELECT *`, `CAST`/`TRY_CAST`, `CROSS JOIN`,
  unfiltered full loads, and unparseable SQL.
- **Local aggregate-only DataSource** over CSV/Parquet (DuckDB) — returns only
  scalar metrics (counts, distinct counts, null counts…), never raw rows.
- **Source–target reconciliation** — row-count drop, empty target, null and
  duplicate primary keys, with quantitative messages.
- **Filter-aware reconciliation** — a row drop explained by a simple `WHERE`
  filter is reported as *expected*, not flagged as loss.
- **Join-aware staged transformation reconciliation** — simple two-table
  INNER/LEFT joins are explained as a staged row-count chain, with advisory
  findings for fan-out, unmatched rows, and null/duplicate join keys.
- **Data-quality profiling** — per-column null / empty-string / distinct rates,
  with all-null, high-null-rate, constant-column, and high-empty-string findings.
- **CLI** (typer) — `list`, `graph`, `check`, `profile`, `stats`.
- **FastAPI API** — `/pipelines/`, `/graph/`, `/findings/`, `/statistics/`,
  `/profile/`.
- **React UI** (Vite + TypeScript + Tailwind + shadcn/ui + React Flow) — five
  pages over a typed API client.

---

## 3. Transformation-aware reconciliation

This is the core idea that distinguishes Open Steward from a plain row-count
check. Instead of flagging *any* difference between source and target as a
problem, Open Steward tries to **explain** the difference using the job's own
SQL, as a staged chain:

```
source_count → after_filter_count → expected_after_join_count → target_count
```

- **`source_count`** — rows in the job's source table.
- **`after_filter_count`** — rows remaining after a simple `WHERE` filter
  (equals `source_count` when there is no filter).
- **`expected_after_join_count`** — rows a simple INNER/LEFT join would produce,
  computed as a scalar `COUNT(*)` over the join (the join result is **never
  materialized**).
- **`target_count`** — actual rows in the target table.

### Simple `WHERE` filters explain expected row loss

For a full-load job like `SELECT * FROM raw.orders WHERE status = 'completed'`,
Open Steward counts how many source rows pass the filter. If the target matches
that count, the drop is **explained** (`row_loss_explained_by_filter`, info) —
no false-positive warning. If the target is below it, that shortfall is flagged
as `unexpected_row_loss`.

### Simple `INNER`/`LEFT` joins explain row loss or row growth

A join can legitimately *reduce* rows (INNER join drops unmatched left rows) or
*increase* them (a non-unique right key multiplies matched rows). Open Steward
computes `expected_after_join_count` and compares it to the target:

| Outcome | Finding |
|---|---|
| `target == expected_after_join_count` | `row_count_change_explained_by_transformations` (info) |
| `target < expected_after_join_count` | `unexpected_row_loss_after_join` (warning) |
| `target > expected_after_join_count` | `unexpected_row_surplus_after_join` (warning) |

### Advisory join findings

Alongside the staged result, Open Steward surfaces *why* the row count moved:

- **`join_unmatched_rows`** — left rows with no matching right key (a warning for
  INNER joins, which drop them; info for LEFT joins, which keep them with NULLs),
  including a `join_match_rate`.
- **`join_key_nulls`** — join keys containing nulls, which never match.
- **`possible_row_multiplication`** — the right join key is not unique, so matched
  left rows can fan out.
- **`possible_many_to_many_join`** — both join keys have duplicates, the classic
  row-multiplication trap.

### Safe fallback over false confidence

Anything not provably simple is **rejected and falls back** rather than producing
a misleading explanation. Open Steward only models: a single `SELECT`; one
two-table `INNER`/`LEFT` join; a single equality `ON` (`a.k = b.k`); and an
optional `WHERE` that uses **only** simple predicates (`=`, `!=`, `<`, `<=`, `>`,
`>=`, `IN`, `IS [NOT] NULL`, `AND`/`OR`) on the **left** table. `RIGHT`/`FULL`/
`CROSS`/`NATURAL`/`USING` joins, multiple joins, composite or non-equality `ON`,
ambiguous unqualified columns, right-table `WHERE`, CTEs, subqueries, `UNION`,
`GROUP BY`/`HAVING`/`DISTINCT`/`LIMIT`, and aggregate/window functions all fall
back to the plain `row_count_drop` behavior with no join findings.

---

## 4. Architecture overview

Open Steward is a Python backend (a shared service layer behind both a CLI and a
REST API) plus a separate React frontend that talks to the API.

```
  ETL config CSV ─────┐
                      ├──►  Backend (FastAPI + typer share one service layer)
  local table         │
  snapshots ──────────┘        adapters/   csv_adapter · DataSource protocol
  (CSV / Parquet)              │           local_file_data_source (DuckDB)
                               │
                               │  services/  graph_builder (NetworkX)
                               │             sql_analyzer (sqlglot)
                               │             reconciliation_engine
                               │               ├─ filter_analyzer
                               │               └─ join_analyzer → join_statistics
                               │             dq_profiler · etl_statistics
                               │             finding_detector
                               │
                               │  api/routes/  /pipelines /graph /findings
                               │               /statistics /profile
                               │  cli.py        list · graph · check · profile · stats
                               ▲
                               │  /api dev proxy (no CORS needed)
                               │
  Frontend (Vite + React + TS) ┘  Overview · Graph (React Flow) · Findings
                                  Statistics · Profile
```

**Layer responsibilities:**

- **Pipeline sources** (`adapters/csv_adapter.py`, `adapters/dbt_manifest_adapter.py`)
  — read job definitions from a config CSV or a dbt manifest into `PipelineJob`
  models via the `PipelineSource` protocol; services never know which one
  produced the jobs.
- **Graph builder** (`services/graph_builder.py`) — builds the NetworkX
  dependency graph, computes execution order, detects cycles.
- **SQL analyzer** (`services/sql_analyzer.py`) — parses each job's `sql_query`
  with sqlglot and flags risky patterns.
- **DataSource protocol** (`adapters/data_source.py`) — an aggregate-only
  interface (counts, distinct counts, null counts, filtered counts, join-output
  counts…). No method returns raw rows.
- **LocalFileDataSource** (`adapters/local_file_data_source.py`) — implements the
  protocol over local CSV/Parquet using an in-memory DuckDB connection.
- **DatabaseDataSource** (`adapters/database_data_source.py`) — the same
  aggregate-only protocol over a DuckDB database file or an attached Postgres
  database. Both database sources share one query implementation
  (`adapters/duckdb_aggregate_source.py`) with the file source — only the
  table→relation resolution differs.
- **Reconciliation engine** (`services/reconciliation_engine.py`) — orchestrates
  per-job source↔target checks and the staged transformation analysis.
- **Filter analyzer** (`services/filter_analyzer.py`) — conservatively extracts a
  simple single-source `WHERE` predicate.
- **Join analyzer / join statistics** (`services/join_analyzer.py`,
  `services/join_statistics.py`) — extract a simple two-table join and compute the
  staged + advisory join findings.
- **DQ profiler** (`services/dq_profiler.py`) — per-column profiling and findings.
- **ETL statistics** (`services/etl_statistics.py`) — per-job numeric metrics
  (the numbers behind reconciliation), exposed for the UI.
- **CLI** (`cli.py`) and **API** (`main.py`, `api/routes/`) — two front doors over
  the same services.
- **Frontend** (`frontend/src/`) — typed API client (`lib/api.ts`), shared config
  context, and the five feature pages.

---

## 5. How to run it locally

> Toolchain: Python 3.11+ and Node 18+ (developed against Python 3.14 and
> Node 24 / npm 11). All commands below are the actual project commands.

### Backend (API + CLI)

```bash
cd backend
pip install -e ".[dev]"
```

Run the backend test suite:

```bash
cd backend
python -m pytest -v
```

Start the FastAPI server (interactive docs at `http://localhost:8000/docs`):

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

> **PATH note:** if the `open-steward` CLI is not found after install, run it as a
> module from the `backend/` directory: `python -m app.cli …` (or `py -m app.cli …`
> on Windows).

### Frontend (UI)

```bash
cd frontend
npm install
npm run dev        # UI at http://localhost:5173 (proxies /api to the backend)
```

Frontend build and tests:

```bash
cd frontend
npm run build      # type-check + production build
npm test           # Vitest unit tests
```

### Run as one app (production-style)

Once the frontend is built (`npm run build`), the FastAPI backend serves the
compiled UI itself — one process, one port:

```bash
cd backend
open-steward serve            # UI + API at http://localhost:8000 (docs at /docs)
open-steward serve --port 9000 --host 0.0.0.0   # options
```

How it works: the built single-page app is served from `frontend/dist` with an
SPA fallback (hard reloads on `/graph`, `/findings`, … load the app), and the
API is aliased under `/api/*` — the same prefix the Vite dev proxy uses — so the
UI works identically in both modes. The bare API paths (`/pipelines/`, …) remain
canonical and unchanged. If the UI hasn't been built, `serve` still runs the API
and tells you how to build the UI.

---

## 6. CLI examples

Run these from the `backend/` directory (using the bundled demo data).

**List all jobs in a config** — what ETLs exist and which are enabled:

```bash
open-steward list --file demo_data/demo_config.csv
```

**Dependency graph & execution order** — includes all jobs (enabled and
disabled) so the full dependency picture is preserved:

```bash
open-steward graph --file demo_data/demo_config.csv
```

**Structural + SQL checks (no data needed)** — risky SQL and graph issues:

```bash
open-steward check --file demo_data/demo_config.csv
```

**Add reconciliation against local snapshots** — row loss, duplicate/null keys,
and transformation-aware explanations:

```bash
open-steward check --file demo_data/demo_config.csv --data-dir demo_data
```

**Per-job ETL statistics** — the numbers behind reconciliation (`—` means
not computable, e.g. a missing snapshot — never zero):

```bash
open-steward stats --file demo_data/demo_config.csv --data-dir demo_data
```

**Profile a table** — per-column data-quality metrics and findings:

```bash
open-steward profile --table staging.orders --data-dir demo_data
```

**From a dbt manifest instead of a CSV** — every command accepts `--manifest`
(exactly one of `--file`/`--manifest`):

```bash
open-steward list  --manifest samples/dbt_manifest_sample.json
open-steward check --manifest samples/dbt_manifest_sample.json --data-dir demo_data
```

**Against a database instead of snapshots** — `--db` takes a DuckDB database
file or a `postgres://` URL (`${ENV_VAR}` placeholders expanded from the
environment; the resolved URL is never logged):

```bash
open-steward stats --file demo_data/demo_config.csv --db warehouse.duckdb
open-steward check --file demo_data/demo_config.csv --db "postgres://steward:${PGPASSWORD}@localhost/warehouse"
```

**Discover tables** — list what a data directory or database contains:

```bash
open-steward tables --data-dir demo_data
open-steward tables --db warehouse.duckdb --output json
```

**Tune the strictness** — tolerances and thresholds (defaults unchanged):

```bash
open-steward check   --file config.csv --data-dir data --row-loss-tolerance 5
open-steward profile --table staging.orders --data-dir data --null-threshold 40 --empty-threshold 25
```

**CI integration** — `--output json` on `list`/`check`/`stats`/`profile` emits
machine-readable output, and `--fail-on warning` makes `check` strict:

```bash
open-steward check --file config.csv --data-dir data --output json --fail-on warning
```

Exit codes: `check` exits `1` on any error-severity finding (or warnings too
with `--fail-on warning`), `profile` exits `1` on error findings, `graph` exits
`1` on a cycle (CI-friendly); `list` and `stats` always exit `0`.
`open-steward --version` prints the version.

---

## 7. API examples

Start the server (`uvicorn app.main:app --reload --port 8000`), then:

```bash
# List jobs / one job (config files are confined to backend/samples/)
curl "http://localhost:8000/pipelines/?file=demo_config.csv"
curl "http://localhost:8000/pipelines/etl_001?file=demo_config.csv"

# Dependency graph + execution order
curl "http://localhost:8000/graph/?file=demo_config.csv"

# Findings — structural + SQL only…
curl "http://localhost:8000/findings/?file=demo_config.csv"
# …and with reconciliation findings (data_dir is confined to backend/demo_data/)
curl "http://localhost:8000/findings/?file=demo_config.csv&data_dir=."

# Per-job ETL statistics
curl "http://localhost:8000/statistics/?file=demo_config.csv&data_dir=."

# Table profile + data-quality findings
curl "http://localhost:8000/profile/?table=staging.orders&data_dir=."
```

| Endpoint | Query params | Returns |
|---|---|---|
| `GET /pipelines/` | `file` *or* `manifest` | All jobs |
| `GET /pipelines/{config_key}` | `file` *or* `manifest` | One job |
| `GET /graph/` | `file` *or* `manifest` | Nodes, edges, execution order, cycle flag |
| `GET /findings/` | `file`/`manifest`, `data_dir` or `db` *(optional)* | Structural + SQL findings; reconciliation findings too when data is given |
| `GET /statistics/` | `file`/`manifest`, `data_dir` or `db` | Per-job statistics |
| `GET /profile/` | `table`, `data_dir` or `db` | Table profile + data-quality findings |
| `GET /configs/` | — | Config CSVs + dbt manifests available in the config directory |
| `GET /tables/` | `data_dir` or `db` | Tables available in the data directory / database |
| `GET /health` | — | `{status, version}` liveness |

Tuning params: `/findings/` accepts `row_loss_tolerance` (0–100, default 0 =
strict) to suppress row-loss warnings at or below that percentage; `/profile/`
accepts `null_threshold` (default 20) and `empty_threshold` (default 10).

Every config endpoint takes exactly one pipeline source: `file` (config CSV) or
`manifest` (dbt manifest.json), both confined to `backend/samples/`. Data comes
from `data_dir` (snapshots) or `db` (a `.duckdb` file confined to
`backend/demo_data/`) — at most one of the two.

**Point the API at your own project:** the config and data roots default to the
bundled `backend/samples/` and `backend/demo_data/`, and can be overridden with
environment variables before starting the server:

```bash
OPEN_STEWARD_CONFIG_DIR=/path/to/your/configs   # config CSVs / dbt manifests
OPEN_STEWARD_DATA_DIR=/path/to/your/data        # snapshots / .duckdb files
```

Path safety: `file`/`manifest` are confined to the config directory, `data_dir`
and `db` to the data root (whatever they're set to), and `table` is validated
against a strict pattern — so the HTTP surface cannot read arbitrary files.
**Database URLs (credentials) are never accepted over the API**; connection
strings are a CLI concern, configured through environment variables. (The CLI
accepts arbitrary local paths.)

---

## 8. UI walkthrough

Run both servers, then open `http://localhost:5173`. The config selector in the
header (default `demo_config.csv`) drives every page.

- **Overview** — confirms the backend connection and lists the configured jobs.
- **Graph** — the pipeline dependency graph (React Flow): table nodes, edges
  labeled with the connecting `config_key`, left-to-right execution layering, and
  a banner if a cycle is detected.
- **Findings** — structural, SQL **and reconciliation** findings (requested
  against the demo snapshots) with error/warning/info summary counts and a
  severity filter.
- **Statistics** — per-job ETL metrics (row counts, loss, primary-key
  null/duplicate counts) with summary cards; `—` for not-computable values.
- **Profile** — profiles a chosen table (default `staging.orders`): table summary,
  a per-column stats table, and data-quality findings.

The UI follows a dark "control-room" design language (see
[`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md)). All screenshots below are captured against
`showcase_config.csv`.

**Overview** — backend connection status and the configured-job roster:

![Overview dashboard reporting a healthy backend connection and the job roster](screenshots/overview-showcase.png)

**Graph** — the dependency graph in source → staging → mart lanes. Edge labels are
hidden by default for a clean canvas and revealed on hover/selection:

![Pipeline graph laid out as source, staging and mart lanes](screenshots/graph-showcase.png)

Clicking an edge or a table opens an inspector with the details available from the
graph payload:

| Edge inspector — config key, source, target | Table inspector — namespace + dependency counts |
|---|---|
| ![Selected dependency edge showing its config key, source and target tables](screenshots/graph-inspector-edge-showcase.png) | ![Selected table showing its namespace and incoming/outgoing dependency counts](screenshots/graph-inspector-node-showcase.png) |

**Findings** — structural, SQL and reconciliation findings together, with severity
summary counts and a filter. Transformation-aware reconciliation findings are
tagged so they stand out:

![Findings console showing transformation-aware reconciliation findings](screenshots/findings-transformations-showcase.png)

The severity filter narrows the feed — e.g. to error-severity issues only:

![Findings console filtered to error-severity issues](screenshots/findings-errors-showcase.png)

**Statistics** — per-job ETL telemetry; `—` marks not-computable values:

![Per-job ETL statistics telemetry panels](screenshots/statistics-showcase.png)

**Profile** — per-column data-quality metrics and findings for a chosen table:

![Table profile with per-column data-quality metrics and findings](screenshots/profile-showcase.png)

---

## 9. Finding types catalog

### Structural findings
| Type | Severity | Meaning |
|---|---|---|
| `circular_dependency` | error | Jobs form a loop — no valid execution order |
| `duplicate_target` | error | Two or more jobs write the same target table |
| `disabled_dependency` | error | An enabled job depends on a disabled job's output |
| `unresolved_upstream` | info | A source table isn't produced by any job or known external prefix |

### SQL findings (sqlglot)
| Type | Severity | Meaning |
|---|---|---|
| `select_star` | warning | `SELECT *` — exposes unexpected columns on schema change |
| `explicit_cast` | warning | `CAST`/`TRY_CAST` — may silently change types |
| `cross_join` | error | Explicit `CROSS JOIN` — likely a cartesian product |
| `missing_filter_on_full_load` | info | Full load with no `WHERE`/`LIMIT` — replaces the whole target |
| `unparseable_sql` | warning | SQL could not be parsed |

### Reconciliation findings
| Type | Severity | Meaning |
|---|---|---|
| `empty_target` | warning | Target is empty while source has rows |
| `row_count_drop` | warning | Full-load target has fewer rows than source, not explained by a filter |
| `null_primary_key` | error | Primary key has nulls in the target |
| `duplicate_primary_key` | error | Primary key is not unique in the target |

### Filter-aware findings
| Type | Severity | Meaning |
|---|---|---|
| `row_loss_explained_by_filter` | info | The drop matches the job's simple `WHERE` filter |
| `unexpected_row_loss` | warning | Target is below the filtered source count |

### Join-aware findings
| Type | Severity | Meaning |
|---|---|---|
| `row_count_change_explained_by_transformations` | info | Target matches the staged filter+join expectation |
| `unexpected_row_loss_after_join` | warning | Fewer rows than the filter+join explain |
| `unexpected_row_surplus_after_join` | warning | More rows than the filter+join explain |
| `join_unmatched_rows` | warning (INNER) / info (LEFT) | Left rows with no matching right key |
| `join_key_nulls` | info | A join key contains nulls (never match) |
| `possible_row_multiplication` | warning | Right join key not unique — matched rows may fan out |
| `possible_many_to_many_join` | warning | Both keys have duplicates — many-to-many fan-out |

### Data profiling findings
| Type | Severity | Meaning |
|---|---|---|
| `all_nulls` | error | Column is entirely null |
| `high_null_rate` | warning | Null rate ≥ 20% |
| `constant_column` | info | Only one distinct value across many rows |
| `high_empty_string_rate` | warning | VARCHAR column ≥ 10% empty strings |

---

## 10. Demo project

The demo lives in `backend/demo_data/` (a config plus local table snapshots) and
in `backend/samples/` (configs used by the API and tests). The demo models a
small four-job e-commerce pipeline:

| Job | Source → Target | Status | Notable SQL |
|---|---|---|---|
| `etl_001` Load Orders | `raw.orders` → `staging.orders` | enabled | `SELECT *` |
| `etl_002` Load Customers | `raw.customers` → `staging.customers` | enabled | `CAST(...)` |
| `etl_003` Enrich Orders | `staging.orders` → `mart.orders_enriched` | enabled | `WHERE status = 'completed'` |
| `etl_004` Daily Revenue | `mart.orders_enriched` → `mart.daily_revenue` | **disabled** | aggregate |

**Issues it intentionally demonstrates:**

- **Row loss** — `raw.orders` (20 rows) → `staging.orders` (18 rows) triggers
  `row_count_drop`.
- **Duplicate primary key** — `staging.customers` has a duplicated `customer_id`,
  triggering `duplicate_primary_key`.
- **High null rate** — `coupon_code` is ~83% null, triggering `high_null_rate` in
  the profile.
- **SQL risks** — `SELECT *` (etl_001), an explicit cast (etl_002), and
  full-load-without-filter info findings.

**What does not change because some snapshots are intentionally missing:**
`mart.orders_enriched` and `mart.daily_revenue` have **no local snapshots**, so
those jobs are silently skipped during reconciliation (missing snapshots are never
treated as errors — reconciliation is opt-in). This is why the `stats` command
shows `—` for `etl_003`'s target-side metrics, and why the documented demo output
stays stable.

---

## 11. Design principles

- **Local-first.** Open Steward runs right next to your data, with a fast local
  setup and no heavyweight infrastructure to stand up.
- **Aggregate-only where possible.** The `DataSource` interface returns scalar
  metrics, not rows. Even join analysis uses scalar `COUNT(*)` queries — the join
  result is never materialized for the caller. This keeps the engine efficient and
  is the seam through which additional data sources can be added.
- **Conservative analysis.** Transformation explanation only applies to provably
  simple SQL shapes.
- **Safe fallback over false confidence.** When SQL is too complex or ambiguous,
  Open Steward falls back to plain behavior rather than emitting a misleading
  explanation. Advisory findings never assert business correctness.
- **Two front doors, one engine.** The CLI and the API share the same services, so
  behavior is consistent.

---

## 12. Current analysis scope

Analysis is intentionally conservative — Open Steward explains what it can prove
and falls back safely otherwise. Current coverage:

- Transformation explanation covers **simple SQL patterns** — a single `SELECT`,
  one two-table INNER/LEFT join, a single equality `ON`, and a simple left-only
  `WHERE`. Complex or multi-join queries, CTEs, subqueries, `UNION`, `GROUP BY`,
  and window functions fall back to plain row-count reconciliation.
- **Single-column join keys** (composite keys not yet covered).
- **`INNER` and `LEFT` joins** (`RIGHT`/`FULL`/`NATURAL`/`USING` not yet covered).
- **Single-column primary keys** in reconciliation/profiling.
- **Multi-parent lineage is preserved in the graph** (dbt models with several
  refs contribute one edge per parent), but reconciliation still models one
  primary source table per job.
- **dbt support** reads a documented subset of `manifest.json` (models, sources,
  seeds, snapshots, and `unique` tests; manifest schemas v10–v12). Ephemeral
  models are resolved through to their parents; models with no resolvable
  upstream are skipped. Prefer a compiled manifest — raw Jinja SQL is flagged
  as unparseable rather than analyzed.
- **Database connectivity** covers DuckDB files (read-only) and Postgres via
  DuckDB's postgres extension (installed automatically on first use).
- Profiling covers columns whose names match `[A-Za-z0-9_]+`.

---

## 13. How to present this project

**What it demonstrates technically:**

- A clean, layered Python backend with a single service layer behind both a CLI
  and a FastAPI service — no logic duplication.
- An aggregate-only data-access abstraction (`DataSource` protocol) designed to be
  connector-ready, implemented over DuckDB for local files.
- Real SQL parsing and AST analysis with sqlglot, applied conservatively.
- A genuinely interesting domain idea — **transformation-aware reconciliation**
  that explains row-count changes through filters and joins rather than just
  flagging differences.
- A typed React + TypeScript frontend (Vite, Tailwind, shadcn/ui, React Flow) with
  a dev proxy and unit tests.
- Strong test discipline: 350+ tests across backend and frontend, including pure
  unit tests for the analysis logic.
- CI, an MIT license, and honest, verified documentation.

**Why it's relevant** for Analytics Engineering / Data Engineering / Data Platform
roles: it speaks directly to the day-to-day concerns of pipeline observability,
data quality, and "did my transformation do what I think it did?" — and shows the
ability to design a small platform end to end (parsing, analysis, API, CLI, UI,
tests, docs).

**Short GitHub description:**
> Local-first pipeline intelligence & data-quality tool for SQL-config ETL:
> dependency graph, SQL risk analysis, transformation-aware reconciliation
> (filter + join), and table profiling — via CLI, FastAPI, and a React UI.

**CV-ready description:**
> Built Open Steward, a local-first pipeline-intelligence tool that parses
> SQL-config ETL pipelines, reconstructs dependencies, analyzes SQL risk with
> sqlglot, and explains row-count changes through filter- and join-aware
> reconciliation over DuckDB — exposed through a typer CLI, a FastAPI service, and
> a typed React/TypeScript UI, with 350+ tests and CI.

---

## 14. Roadmap / possible future work

Future ideas only — none of these are implemented yet:

- Composite and multi-join transformation support; `RIGHT`/`FULL` joins;
  post-join `WHERE`.
- Additional adapters and connectors (ADF, dbt `catalog.json`/freshness,
  Snowflake/BigQuery).
- Richer UI: optional charts and trend views; dbt manifests selectable from the UI.
- Configurable thresholds and per-job row-loss tolerances; `--output json` on the
  CLI.
