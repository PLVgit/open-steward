# Open Steward — Frontend

React + TypeScript + Vite frontend for the Open Steward UI. Styled with Tailwind
and shadcn/ui primitives. Includes the app shell, navigation, routing, a typed
API client, and the feature pages: **Overview** (backend connection),
**Pipeline Graph**, **Findings**, **ETL Statistics**, and **Table Profile**.

The Table Profile page consumes the backend `GET /profile/?table=…&data_dir=…`
endpoint (added alongside this page; it reuses the `dq_profiler` service and
returns the table profile plus its data-quality findings).

The graph is rendered with **[`@xyflow/react`](https://reactflow.dev)** (React
Flow v12 — the current, actively maintained package; the older `reactflow` v11
is in maintenance mode). Node positions come from a small custom layered layout
(`src/lib/graphLayout.ts`), so no graph-layout dependency (e.g. dagre) is needed.

## Prerequisites

- Node.js 18+ (developed against Node 24 / npm 11)
- The backend running locally (see `../backend/README.md`)

## Running locally

The frontend talks to the backend through a relative `/api` prefix. In
development, Vite proxies `/api` to the backend, so **no backend CORS
configuration is required**.

**1. Start the backend** (in `../backend`, on port 8000):

```bash
cd ../backend
uvicorn app.main:app --reload --port 8000
```

**2. Start the frontend** (in this directory):

```bash
npm install
npm run dev
```

Open the printed URL (default http://localhost:5173). The Overview page should
report "Connected." and list the jobs from the selected config.

### Backend base URL

The proxy target defaults to `http://localhost:8000`. To point at a different
backend, set `VITE_BACKEND_URL` before `npm run dev`:

```bash
VITE_BACKEND_URL=http://localhost:9000 npm run dev   # macOS/Linux
$env:VITE_BACKEND_URL="http://localhost:9000"; npm run dev   # PowerShell
```

The config file read by the API is selected in the header (defaults to
`demo_config.csv`). It must exist in the backend's `samples/` directory.

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Start the Vite dev server with the backend proxy |
| `npm run build` | Type-check and build for production |
| `npm run preview` | Preview the production build |
| `npm test` | Run the Vitest unit tests once |
| `npm run test:watch` | Run Vitest in watch mode |

## Structure

```text
src/
  components/
    ui/                # shadcn primitives (button, card, badge)
    graph/
      PipelineFlow.tsx # React Flow wrapper
    AppShell.tsx       # sidebar nav + layout
  context/
    ConfigContext.tsx  # selected config file (shared by all pages)
  lib/
    api.ts             # typed API client (/api/*)
    graphLayout.ts     # pure GraphResponse -> React Flow nodes/edges
    findings.ts        # pure summary/filter helpers
    statistics.ts      # pure summary + null-aware formatters
    types.ts           # TypeScript mirrors of backend models
    utils.ts           # cn() class helper
  pages/
    OverviewPage.tsx   # backend connection check
    GraphPage.tsx      # pipeline dependency graph
    FindingsPage.tsx   # structural / SQL findings dashboard
    StatisticsPage.tsx # per-job ETL statistics
    ProfilePage.tsx    # table data-quality profile
  App.tsx              # routes
  main.tsx             # entry
```
