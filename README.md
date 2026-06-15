# Open Steward

> **Local-first pipeline intelligence and data-quality platform for SQL-config-driven ETL workflows.**

`Python` · `FastAPI` · `DuckDB` · `sqlglot` · `NetworkX` · `Typer` — `React` · `TypeScript` · `React Flow`

**Local-first** · **Aggregate-only analysis** · **CLI + REST API + UI** · **~290 tests** · **MIT licensed**

![Open Steward pipeline dependency graph in the control-room UI](docs/screenshots/graph-showcase.png)

Open Steward reads SQL-config-driven ETL pipeline definitions, reconstructs the
dependencies between jobs and tables, computes execution order, flags risky SQL
transformations, **explains** row-count changes through filters and joins, and
profiles final tables for data-quality issues — all from a simple CSV config plus
optional local table snapshots, and all running right next to your data.

---

## The problem

SQL-config-driven ETL pipelines (a metadata table or CSV of jobs, each with a
`source_table`, `target_table`, and a `sql_query`) get hard to reason about as
they grow:

- **What runs, and in what order?** Dependencies are implicit in the source/target tables.
- **Which transformations are risky?** `SELECT *`, casts, cross joins, and unfiltered full loads hide in a long config.
- **Did the data survive?** A job can silently drop rows, duplicate primary keys, or fan rows out through a join.
- **Is the final table clean?** High null rates, empty strings, and constant columns hide in the output.

Open Steward helps an Analytics Engineer **inspect and explain** these issues
*before* they reach downstream consumers.

---

## Features

### 🔗 Pipeline graph & dependency intelligence

A table-level dependency graph (NetworkX) with computed execution order and cycle
detection, rendered as an interactive control-room canvas (React Flow). Lanes flow
**source → staging → mart**; edge labels stay hidden for a clean overview and
reveal on interaction.

![Pipeline graph laid out as source, staging and mart lanes](docs/screenshots/graph-showcase.png)

Hover or click an edge or a table to open the inspector — the **edge inspector**
(left) shows a dependency's config key, source and target; the **table inspector**
(right) shows a table's namespace and incoming/outgoing dependency counts:

<p align="center">
  <img src="docs/screenshots/graph-inspector-edge-showcase.png" width="49%" alt="Selected dependency edge showing its config key, source and target" />
  <img src="docs/screenshots/graph-inspector-node-showcase.png" width="49%" alt="Selected table showing its namespace and dependency counts" />
</p>

### 🔬 Transformation-aware reconciliation

The headline capability. Instead of flagging *any* source↔target difference, Open
Steward tries to **explain** it from the job's own SQL as a staged chain:

```
source_count → after_filter_count → expected_after_join_count → target_count
```

A simple `WHERE` filter explains expected row loss; a simple INNER/LEFT join
explains expected loss or fan-out. Anything that matches the expectation is
reported as *explained* (info); only the unexplained delta is flagged.

![Findings console showing transformation-aware reconciliation findings](docs/screenshots/findings-transformations-showcase.png)

### 🚨 Findings / issue console

Structural, SQL, **and** reconciliation findings in one feed, with severity
summary counts and a filter. Each finding carries its type, affected job/table,
message, and recommendation.

![Findings console filtered to error-severity issues](docs/screenshots/findings-errors-showcase.png)

### 📊 ETL statistics

Per-job numeric metrics behind reconciliation — row counts, row loss, primary-key
null/duplicate counts. Not-computable values render as `—`, never as `0`.

![Per-job ETL statistics telemetry panels](docs/screenshots/statistics-showcase.png)

### 🧪 Data-quality profiling

Per-column null / empty-string / distinct rates for a target table, with
all-null, high-null-rate, constant-column, and high-empty-string findings.

![Table profile with per-column data-quality metrics and findings](docs/screenshots/profile-showcase.png)

---

## Tech stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.11+, FastAPI, Pydantic, Typer (CLI) |
| **Analysis engines** | NetworkX (graph + execution order), sqlglot (SQL AST), DuckDB (aggregate queries over CSV/Parquet) |
| **Frontend** | React, TypeScript, Vite, Tailwind, shadcn/ui, React Flow (`@xyflow/react`) |
| **Quality** | pytest + Vitest (~290 tests), GitHub Actions CI |

---

## Quick start

> Requires Python 3.11+ and Node 18+.

**1. Backend (API + CLI)**

```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000     # API + docs at http://localhost:8000/docs
```

The `pip install` adds an `open-steward` command. The CLI can be invoked three
equivalent ways — all run from the `backend/` directory:

```bash
open-steward --help        # installed entry point
python -m app.cli --help   # module fallback (if the command isn't on PATH)
py -m app.cli --help       # Windows launcher fallback
```

**2. Frontend (UI)**

```bash
cd frontend
npm install
npm run dev                                    # UI at http://localhost:5173
```

With the backend running, the **Overview** page reports "Connected." and lists the
jobs. The config selector in the header drives every page.

![Overview dashboard reporting a healthy backend connection and the job roster](docs/screenshots/overview-showcase.png)

---

## Showcase demo

A synthetic `showcase_config.csv` exercises **every** analysis capability —
structural, SQL, filter- and join-aware reconciliation, and profiling — with
predictable row-count causality.

```bash
# from backend/ (swap open-steward for "python -m app.cli" / "py -m app.cli" if needed)
open-steward check   --file samples/showcase_config.csv --data-dir demo_data
open-steward stats   --file samples/showcase_config.csv --data-dir demo_data
open-steward profile --table showcase_staging.orders_loaded --data-dir demo_data
```

In the UI, set the header **Config** field to `showcase_config.csv` and every page
reflects the showcase. Full walkthrough: [`docs/SHOWCASE_WALKTHROUGH.md`](docs/SHOWCASE_WALKTHROUGH.md).

---

## Architecture

The CLI and the REST API share one Python service layer; the React UI talks to the
API through a dev proxy (no CORS setup needed).

```
  ETL config CSV ─────┐
                      ├──►  Backend (FastAPI + Typer share one service layer)
  local table         │
  snapshots ──────────┘     adapters/   csv_adapter · DataSource (aggregate-only, DuckDB)
  (CSV / Parquet)           services/   graph_builder (NetworkX) · sql_analyzer (sqlglot)
                            │           reconciliation_engine ─ filter_analyzer
                            │                                 └ join_analyzer · join_statistics
                            │           dq_profiler · etl_statistics · finding_detector
                            │           ──────────────────────────────────────────────
                            │  api/routes/  /pipelines /graph /findings /statistics /profile
                            │  cli.py        list · graph · check · profile · stats
                            ▲
                            │  /api dev proxy
                            │
   Frontend (Vite/React/TS) ┘  Overview · Graph (React Flow) · Findings · Statistics · Profile
```

Component docs: [`backend/README.md`](backend/README.md) · [`frontend/README.md`](frontend/README.md).

---

## Design principles

- **Local-first** — runs right next to your data, fast setup, no infrastructure to stand up.
- **Aggregate-only where possible** — the `DataSource` interface returns scalar metrics, never raw rows; even join analysis uses scalar `COUNT(*)` (the join is never materialized).
- **Conservative analysis** — transformation explanation only applies to provably simple SQL shapes.
- **Safe fallback over false confidence** — ambiguous SQL falls back to plain row-count reconciliation rather than emitting a misleading explanation.

---

## Current limitations

- No live database connectors yet — analysis runs over a config CSV plus local CSV/Parquet snapshots.
- No dbt or ADF adapters yet.
- Transformation explanation covers **simple SQL only** — a single `SELECT`, one two-table INNER/LEFT join, a single equality `ON`, and a simple left-side `WHERE`. More complex SQL falls back to plain reconciliation.
- Single-column primary and join keys.

---

## Roadmap

| Area | Planned |
|---|---|
| **Adapters** | dbt adapter; ADF / config-source adapter |
| **Connectivity** | live database connectors |
| **Reconciliation** | composite join keys; RIGHT/FULL joins; multi-join and post-join `WHERE` |
| **Configuration** | richer, configurable thresholds and row-loss tolerances |

---

## Documentation

- 📖 [`docs/OPEN_STEWARD_GUIDE.md`](docs/OPEN_STEWARD_GUIDE.md) — full guide: what it does, architecture, the reconciliation model, and the finding catalog.
- 🧪 [`docs/SHOWCASE_WALKTHROUGH.md`](docs/SHOWCASE_WALKTHROUGH.md) — reproducible showcase demo: step-by-step CLI / API / UI tour with expected findings.
- 🎨 [`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md) — the control-room UI design system.

---

## License

[MIT](LICENSE) © 2026 Pol López Vidaller. Open source — contributions and forks welcome.
