# Open Steward

> A local-first pipeline intelligence and virtual data steward for Analytics Engineers.

Open Steward reads SQL-config-driven ETL pipeline definitions, reconstructs the
dependencies between jobs and tables, computes execution order, flags risky SQL
transformations, reconciles source vs. target table data, and profiles final
tables for data-quality issues — from a simple CSV config plus optional local
table snapshots. It ships as a **FastAPI backend**, a **typer CLI**, and a
**React + TypeScript UI**.

**Local-first and demo-data based.** Everything runs on your machine against a
bundled demo dataset (or your own CSV/Parquet snapshots). There are no cloud
services, no live database connections, and no authentication in the current
release. This is an open-source portfolio project, not a production system —
see [Limitations](#limitations).

---

## Screenshots

> 📸 **Screenshots pending capture.** See [`docs/screenshots/README.md`](docs/screenshots/README.md)
> for how to capture them. The links below resolve once the PNGs are added.

| Page | Preview |
|---|---|
| Pipeline Graph | ![Pipeline graph — screenshot pending](docs/screenshots/graph.png) |
| Findings | ![Findings dashboard — screenshot pending](docs/screenshots/findings.png) |
| ETL Statistics | ![ETL statistics — screenshot pending](docs/screenshots/statistics.png) |
| Table Profile | ![Table profile — screenshot pending](docs/screenshots/profile.png) |

---

## Architecture

```
ETL config CSV ──┐
                 ├─►  FastAPI backend                         React + TypeScript UI
local table      │      adapters/   CSV + DuckDB file reader     Vite · Tailwind · shadcn/ui
snapshots  ──────┘      services/   graph · sql · reconcile · profile · stats
(CSV / Parquet)         api/        /pipelines /graph /findings /statistics /profile
                        models/     PipelineJob · Finding · JobStatistics · TableProfile
                            ▲                                          │
                            └────────── /api dev proxy ◄───────────────┘
                        CLI (typer): list · graph · check · profile · stats
```

- **Backend** — Python 3.11+, FastAPI, Pydantic. Core engines: **NetworkX**
  (dependency graph + execution order), **sqlglot** (SQL risk analysis),
  **DuckDB** (aggregate queries over local CSV/Parquet). Same services power
  both the CLI and the REST API.
- **Frontend** — React + TypeScript (Vite), Tailwind + shadcn/ui, **React Flow**
  (`@xyflow/react`) for the graph. Talks to the backend through a `/api` dev
  proxy, so no backend CORS configuration is needed.

Component docs: [`backend/README.md`](backend/README.md) ·
[`frontend/README.md`](frontend/README.md).

---

## Quick start

### 1. Backend (API + CLI)

```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000     # API at http://localhost:8000/docs
```

> **Windows / PATH note:** if the `open-steward` CLI is not found after install,
> run it as `python -m app.cli` from the `backend/` directory.

### 2. Frontend (UI)

```bash
cd frontend
npm install
npm run dev                                    # UI at http://localhost:5173
```

Open the printed URL. With the backend running, the **Overview** page reports
"Connected." and lists the demo jobs. The config selector in the header defaults
to `demo_config.csv`.

---

## CLI demo walkthrough

The `backend/demo_data/` directory holds a small e-commerce pipeline config plus
local table snapshots. Run these from the `backend/` directory.

The demo models a four-job pipeline:

| Job | Source | Target | Status |
|-----|--------|--------|--------|
| `etl_001` — Load Orders | `raw.orders` | `staging.orders` | enabled |
| `etl_002` — Load Customers | `raw.customers` | `staging.customers` | enabled |
| `etl_003` — Enrich Orders | `staging.orders` | `mart.orders_enriched` | enabled |
| `etl_004` — Daily Revenue | `mart.orders_enriched` | `mart.daily_revenue` | **disabled** |

**List jobs** — `open-steward list --file demo_data/demo_config.csv`

**Dependency graph & execution order** — `open-steward graph --file demo_data/demo_config.csv`

**Structural + SQL checks (no data needed)** — `open-steward check --file demo_data/demo_config.csv`

**Add reconciliation against local snapshots** — `open-steward check --file demo_data/demo_config.csv --data-dir demo_data`
finds a `duplicate_primary_key` error in `staging.customers` and a
`row_count_drop` warning on `staging.orders` (20 → 18 rows).

**Per-job ETL statistics** — `open-steward stats --file demo_data/demo_config.csv --data-dir demo_data`

```
Open Steward  ·  demo_config.csv  ·  3 enabled jobs

KEY      TARGET                SOURCE   TARGET#  LOST    LOSS%    PK NULLS  PK DUPS
etl_001  staging.orders        20       18       2       10.0%    0         0
etl_002  staging.customers     10       11       0       0.0%     0         1
etl_003  mart.orders_enriched  18       —        —       —        —         —

Statistics describe what happened numerically; run 'check' for findings.
```

`—` means *not computable* (here, `mart.orders_enriched` has no local snapshot) —
it does **not** mean zero.

**Profile a table** — `open-steward profile --table staging.orders --data-dir demo_data`
reports per-column null/empty/distinct rates and flags `coupon_code` (83.3% null).

Full command output and the finding catalog live in
[`backend/README.md`](backend/README.md#demo-walkthrough).

---

## UI tour

Run both servers (above), then visit each page. The selected config file (header)
drives every page.

- **Overview** — confirms the backend connection and lists the configured jobs
  (enabled/disabled). Your "is everything wired up?" page.
- **Graph** — the pipeline dependency graph rendered with React Flow. Table nodes,
  edges labeled with the `config_key` that connects them, left-to-right execution
  layering, and a banner if a circular dependency is detected.
- **Findings** — structural, SQL **and reconciliation** findings (the dashboard
  requests them against the demo snapshots), with error/warning/info summary
  counts and a severity filter. Each finding shows its type, affected job/table,
  message, and recommendation.
- **Statistics** — per-job ETL metrics (row counts, row loss, primary-key
  null/duplicate counts) with summary cards. Missing/not-computable values render
  as `—`, never as `0`.
- **Profile** — profiles a chosen table (default `staging.orders`): table summary,
  a per-column stats table, and data-quality findings (e.g. high null rate).

---

## What Open Steward can do today

- Parse a SQL-config-driven ETL pipeline from a CSV.
- Build the table dependency graph, compute execution order, and detect cycles,
  duplicate targets, disabled-dependency and unresolved-upstream issues.
- Analyze each job's SQL with sqlglot: `SELECT *`, `CAST`/`TRY_CAST`,
  `CROSS JOIN`, and full-load-without-filter risks.
- Reconcile source vs. target snapshots: row-count drop, empty target, null and
  duplicate primary keys — with quantitative messages. **Filter-aware:** a row
  drop explained by a simple `WHERE` filter is reported as expected rather than
  flagged as loss.
- Profile target tables per column (null / empty-string / distinct rates) and
  flag all-null, high-null-rate, constant-column, and high-empty-string columns.
- Expose all of the above over a REST API **and** a CLI, plus a five-page React UI.

---

## Limitations

Open Steward is an honest MVP. It does **not** (yet) do the following:

- **One source table per job.** `PipelineJob.source_table` is a single string;
  multi-source joins are only partially modeled (the raw SQL is preserved for
  analysis).
- **Single-column primary keys only** for reconciliation/profiling.
- **Local snapshots only.** Reconciliation and profiling read local CSV/Parquet
  files — there is no live database connection.
- **Demo-data based.** The bundled demo drives the walkthrough and the UI; point
  `--data-dir` at your own exported snapshots to use real data locally.
- **Column-name restrictions.** Profiling skips columns whose names are not
  `[A-Za-z0-9_]+`.
- **Dev-only frontend wiring.** The UI reaches the backend through the Vite dev
  proxy; production serving/build, deployment, and hosting are out of scope.
- **No authentication, multi-tenancy, scheduling, or alerting.** Single-user,
  local, on-demand.

---

## Roadmap

**Next**
- **Join-aware advisory statistics** — `join_match_rate`, unmatched rows, and
  possible row multiplication, surfaced as advisory (not hard errors). This is
  also where row *surplus* (target with more rows than a filter explains) will be
  handled.

**Shipped recently**
- **Filter-aware reconciliation** — a full-load row drop explained by a simple
  single-source `WHERE` filter is reported as expected (`row_loss_explained_by_filter`)
  instead of a false-positive `row_count_drop`; a shortfall below the filtered
  count is flagged as `unexpected_row_loss`.

**Later**
- dbt adapter (read model definitions as pipeline jobs).
- Azure Data Factory metadata/log adapter.
- Read-only live database connectors (e.g. Postgres, Snowflake).
- Distribution / histogram profiling (e.g. via Polars).
- `--output json` on all CLI commands; configurable thresholds and row-loss
  tolerances.

---

## License

[MIT](LICENSE) © 2026 Pol López Vidaller. Open source — contributions and forks
welcome.
