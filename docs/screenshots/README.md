# Screenshots — capture guide

The root `README.md` references the images below. They are **not yet captured** —
capture them manually by running the app, then drop the PNGs into this folder
with the exact filenames listed.

## How to capture

1. Start the backend:
   ```bash
   cd backend
   uvicorn app.main:app --reload --port 8000
   ```
2. Start the frontend:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
3. Open the printed URL (default http://localhost:5173). The config selector in
   the header should read `demo_config.csv`.
4. Capture each page at a reasonable window width (~1280px) and save as PNG.

## Required images

| Filename | Page | What it should show |
|---|---|---|
| `overview.png` | Overview (`/`) | "Connected." status and the demo job list |
| `graph.png` | Graph (`/graph`) | The pipeline dependency graph with labeled edges |
| `findings.png` | Findings (`/findings`) | Summary counts, severity filter, and a few finding cards |
| `statistics.png` | Statistics (`/statistics`) | Summary cards and per-job metric cards (with an `—` value visible) |
| `profile.png` | Profile (`/profile`) | `staging.orders` table summary, column-stats table, and the high-null-rate finding |

Until these files exist, the README image links will show their alt text
("screenshot pending").
