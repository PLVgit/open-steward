# Open Steward — Backend

Local-first pipeline intelligence for Analytics Engineers.

Scans SQL-config-driven ETL pipelines, reconstructs dependencies, detects structural issues and validates data quality.

---

## Setup

```bash
cd backend
pip install -e ".[dev]"
```

---

## CLI

### Check a pipeline config for structural issues

```bash
open-steward check --file /path/to/etl_config.csv
```

Prints findings grouped by severity (errors, warnings, info).  
Exits with code `1` if any errors are found — useful in CI pipelines.

### List all ETL jobs

```bash
open-steward list --file /path/to/etl_config.csv
```

### Show execution order

```bash
open-steward graph --file /path/to/etl_config.csv
```

Prints the topological execution order of pipeline tables.  
Exits with code `1` and reports the affected tables if a cycle is detected.

### Using the sample config

```bash
open-steward check --file backend/samples/sample_config.csv
open-steward list  --file backend/samples/sample_config.csv
open-steward graph --file backend/samples/sample_config.csv
```

---

## API

Start the development server:

```bash
cd backend
uvicorn app.main:app --reload
```

Endpoints (all accept `?file=<filename>` — files must be in `backend/samples/`):

| Method | Path | Description |
|--------|------|-------------|
| GET | `/pipelines/` | List all jobs |
| GET | `/pipelines/{config_key}` | Get one job |
| GET | `/graph/` | Dependency graph and execution order |
| GET | `/findings/` | All structural findings |

Example:

```bash
curl "http://localhost:8000/findings/?file=sample_config.csv"
```

---

## Tests

```bash
cd backend
python -m pytest -v
```
