# Screenshots

Canonical screenshots of the Open Steward UI, used by the root [`README.md`](../../README.md)
and the docs in [`../`](../). All are captured against `showcase_config.csv` using
the dark control-room theme (see [`../DESIGN_SYSTEM.md`](../DESIGN_SYSTEM.md#8-screenshot-standards)).

## Inventory

| File | Page / view |
|---|---|
| `overview-showcase.png` | Overview — connection status + job roster |
| `graph-showcase.png` | Graph — source → staging → mart lanes (default, edge labels hidden) |
| `graph-inspector-edge-showcase.png` | Graph — selected-edge inspector (config key, source, target) |
| `graph-inspector-node-showcase.png` | Graph — selected-table inspector (namespace, dependency counts) |
| `findings-transformations-showcase.png` | Findings — transformation-aware reconciliation results |
| `findings-errors-showcase.png` | Findings — filtered to error severity |
| `statistics-showcase.png` | Statistics — per-job ETL telemetry |
| `profile-showcase.png` | Profile — `showcase_staging.orders_loaded` |

## Re-capturing

1. Start the backend (`uvicorn app.main:app --reload --port 8000` from `backend/`).
2. Start the frontend (`npm run dev` from `frontend/`) and open the printed URL.
3. Set the header **Config** field to `showcase_config.csv`.
4. Capture each page at ~1280px width and save as PNG with the filename above.
