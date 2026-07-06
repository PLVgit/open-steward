import sys
from pathlib import Path

import typer

from app.adapters.csv_adapter import CsvAdapter
from app.adapters.data_source import DataSource
from app.adapters.database_data_source import DatabaseDataSource
from app.adapters.dbt_manifest_adapter import DbtManifestAdapter
from app.adapters.local_file_data_source import LocalFileDataSource
from app.models.finding import ValidationFinding
from app.models.job_statistics import JobStatistics
from app.models.pipeline_job import PipelineJob
from app.models.table_profile import TableProfile
from app.services.dq_profiler import detect_profile_findings, profile_table
from app.services.etl_statistics import compute_job_statistics
from app.services.finding_detector import detect_findings
from app.services.graph_builder import build_graph, detect_cycles, get_execution_order
from app.services.reconciliation_engine import reconcile_jobs

# On Windows, output redirected to a file/pipe defaults to the legacy locale
# codepage (e.g. cp1252), which cannot encode the arrows/checkmarks in CLI
# output and crashes with UnicodeEncodeError. Force UTF-8 — a no-op where the
# stream is already UTF-8 (interactive consoles, Linux/macOS, CI).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

app = typer.Typer(
    name="open-steward",
    help="Open Steward — pipeline intelligence for Analytics Engineers.",
    add_completion=False,
)


# ── shared loaders ────────────────────────────────────────────────────────────

# Reused option declarations: pipeline definitions come from exactly one of a
# config CSV (--file) or a dbt manifest (--manifest).
FILE_OPT = typer.Option(None, "--file", "-f", help="Path to ETL config CSV")
MANIFEST_OPT = typer.Option(None, "--manifest", "-m", help="Path to a dbt manifest.json")


def _load_jobs(file: Path | None, manifest: Path | None) -> tuple[list[PipelineJob], Path]:
    """Load jobs from exactly one pipeline source; returns (jobs, source path)."""
    if (file is None) == (manifest is None):
        typer.echo("Error: provide exactly one of --file or --manifest.", err=True)
        raise typer.Exit(code=2)
    path = file if file is not None else manifest
    adapter = CsvAdapter(str(file)) if file is not None else DbtManifestAdapter(str(manifest))
    try:
        return adapter.load(), path
    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)


def _make_data_source(data_dir: Path | None, db: str | None) -> DataSource | None:
    """Build a DataSource from --data-dir (snapshots) or --db (database file or
    postgres:// URL, ${ENV_VAR} placeholders expanded). None when neither given."""
    if data_dir is not None and db is not None:
        typer.echo("Error: provide only one of --data-dir or --db.", err=True)
        raise typer.Exit(code=2)
    if db is not None:
        try:
            return DatabaseDataSource(db)
        except FileNotFoundError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1)
    if data_dir is not None:
        return LocalFileDataSource(data_dir)
    return None


def _header(file: Path, suffix: str = "") -> None:
    label = f"Open Steward  ·  {file.name}"
    if suffix:
        label += f"  ·  {suffix}"
    typer.echo(typer.style(label, bold=True))
    typer.echo()


# ── renderers (add _render_*_json counterparts here when --output json lands) ─

def _render_check_text(findings: list[ValidationFinding], file: Path) -> int:
    _header(file)

    if not findings:
        typer.echo(typer.style("No findings.  ✓", fg=typer.colors.GREEN))
        typer.echo()
        typer.echo("0 errors · 0 warnings · 0 info")
        return 0

    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]
    infos = [f for f in findings if f.severity == "info"]

    def _group(items: list[ValidationFinding], label: str, color: str) -> None:
        if not items:
            typer.echo(typer.style(f"No {label.lower()}.", fg=typer.colors.GREEN))
            typer.echo()
            return
        typer.echo(typer.style(f"{label} ({len(items)})", fg=color, bold=True))
        typer.echo()
        for f in items:
            loc = f.affected_table or f.affected_job or ""
            typer.echo(f"  [{f.finding_type}]  {loc}")
            typer.echo(f"  {f.message}")
            if f.recommendation:
                typer.echo(f"  → {f.recommendation}")
            typer.echo()

    _group(errors, "ERRORS", typer.colors.RED)
    _group(warnings, "WARNINGS", typer.colors.YELLOW)
    _group(infos, "INFO", typer.colors.BRIGHT_BLACK)

    typer.echo("─" * 48)
    typer.echo(f"{len(errors)} errors · {len(warnings)} warnings · {len(infos)} info")
    return 1 if errors else 0


def _render_list_text(jobs: list[PipelineJob], file: Path) -> None:
    enabled_count = sum(1 for j in jobs if j.enabled)
    _header(file, f"{len(jobs)} jobs ({enabled_count} enabled)")

    w_key = max(len("KEY"), *(len(j.config_key) for j in jobs)) + 2
    w_name = max(len("NAME"), *(len(j.pipeline_name) for j in jobs)) + 2
    w_src = max(len("SOURCE"), *(len(j.source_table) for j in jobs)) + 2
    w_tgt = max(len("TARGET"), *(len(j.target_table) for j in jobs)) + 2

    def _row(key: str, name: str, enabled: str, src: str, tgt: str, load: str) -> str:
        return f"{key:<{w_key}}{name:<{w_name}}{enabled:<9}{src:<{w_src}}{tgt:<{w_tgt}}{load}"

    typer.echo(typer.style(_row("KEY", "NAME", "ENABLED", "SOURCE", "TARGET", "LOAD"), bold=True))
    for j in jobs:
        typer.echo(_row(
            j.config_key,
            j.pipeline_name,
            "yes" if j.enabled else "no",
            j.source_table,
            j.target_table,
            j.load_type or "-",
        ))


def _render_graph_text(graph, file: Path) -> int:
    _header(file, "execution order")

    cycles = detect_cycles(graph)
    if cycles:
        typer.echo(typer.style(
            "✗  Cycle detected — execution order cannot be determined.",
            fg=typer.colors.RED, bold=True,
        ))
        for cycle in cycles:
            typer.echo("   " + " → ".join(cycle + [cycle[0]]))
        return 1

    for i, table in enumerate(get_execution_order(graph), 1):
        typer.echo(f" {i:>2}   {table}")
    typer.echo()
    typer.echo(typer.style("No cycles detected.  ✓", fg=typer.colors.GREEN))
    return 0


# ── commands ──────────────────────────────────────────────────────────────────

@app.command()
def check(
    file: Path | None = FILE_OPT,
    manifest: Path | None = MANIFEST_OPT,
    data_dir: Path | None = typer.Option(
        None, "--data-dir", "-d",
        help="Directory of local table snapshots for reconciliation (optional).",
    ),
    db: str | None = typer.Option(
        None, "--db",
        help="Database for reconciliation: a DuckDB file or a postgres:// URL (optional).",
    ),
) -> None:
    """Run all structural checks and report findings."""
    jobs, path = _load_jobs(file, manifest)
    graph = build_graph(jobs)
    findings = detect_findings(jobs, graph)
    data_source = _make_data_source(data_dir, db)
    if data_source is not None:
        findings = findings + reconcile_jobs(jobs, data_source)
    code = _render_check_text(findings, path)
    raise typer.Exit(code=code)


@app.command(name="list")
def list_jobs(
    file: Path | None = FILE_OPT,
    manifest: Path | None = MANIFEST_OPT,
) -> None:
    """List all ETL jobs in the config."""
    jobs, path = _load_jobs(file, manifest)
    _render_list_text(jobs, path)


@app.command()
def graph(
    file: Path | None = FILE_OPT,
    manifest: Path | None = MANIFEST_OPT,
) -> None:
    """Show the pipeline dependency graph and execution order."""
    jobs, path = _load_jobs(file, manifest)
    g = build_graph(jobs)
    code = _render_graph_text(g, path)
    raise typer.Exit(code=code)


def _render_profile_text(tbl: TableProfile, findings: list[ValidationFinding]) -> int:
    typer.echo(typer.style(f"Open Steward  ·  {tbl.table_name}  ·  profile", bold=True))
    typer.echo()
    typer.echo(f"{tbl.row_count} rows · {tbl.column_count} columns")
    typer.echo()

    if tbl.columns:
        w_col = max(len("COLUMN"), *(len(c.column_name) for c in tbl.columns)) + 2
        w_dtype = max(len("DTYPE"), *(len(c.dtype) for c in tbl.columns)) + 2

        typer.echo(typer.style(
            f"{'COLUMN':<{w_col}}{'DTYPE':<{w_dtype}}{'NULLS':<9}{'EMPTY':<9}DISTINCT",
            bold=True,
        ))
        for col in tbl.columns:
            empty_str = f"{col.empty_string_pct}%" if col.empty_string_pct is not None else "—"
            typer.echo(
                f"{col.column_name:<{w_col}}{col.dtype:<{w_dtype}}"
                f"{col.null_pct}%{'':<{8 - len(str(col.null_pct))}}"
                f"{empty_str:<9}{col.distinct_pct}%"
            )
        typer.echo()

    if not findings:
        typer.echo(typer.style("No findings.  ✓", fg=typer.colors.GREEN))
        typer.echo()
        typer.echo("0 errors · 0 warnings · 0 info")
        return 0

    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]
    infos = [f for f in findings if f.severity == "info"]

    def _group(items: list[ValidationFinding], label: str, color: str) -> None:
        if not items:
            return
        typer.echo(typer.style(f"{label} ({len(items)})", fg=color, bold=True))
        typer.echo()
        for f in items:
            typer.echo(f"  [{f.finding_type}]  {f.affected_table or ''}")
            typer.echo(f"  {f.message}")
            if f.recommendation:
                typer.echo(f"  → {f.recommendation}")
            typer.echo()

    typer.echo("─" * 48)
    _group(errors, "ERRORS", typer.colors.RED)
    _group(warnings, "WARNINGS", typer.colors.YELLOW)
    _group(infos, "INFO", typer.colors.BRIGHT_BLACK)
    typer.echo("─" * 48)
    typer.echo(f"{len(errors)} errors · {len(warnings)} warnings · {len(infos)} info")
    return 1 if errors else 0


def _render_stats_text(stats: list[JobStatistics], file: Path) -> None:
    _header(file, f"{len(stats)} enabled jobs")

    if not stats:
        typer.echo("No enabled jobs to report.")
        return

    def _num(value: int | None) -> str:
        return "—" if value is None else str(value)

    def _pct(value: float | None) -> str:
        return "—" if value is None else f"{value}%"

    w_key = max(len("KEY"), *(len(s.config_key) for s in stats)) + 2
    w_tgt = max(len("TARGET"), *(len(s.target_table) for s in stats)) + 2

    header = (
        f"{'KEY':<{w_key}}{'TARGET':<{w_tgt}}"
        f"{'SOURCE':<9}{'TARGET#':<9}{'LOST':<8}{'LOSS%':<9}"
        f"{'PK NULLS':<10}{'PK DUPS':<9}"
    )
    typer.echo(typer.style(header, bold=True))
    for s in stats:
        typer.echo(
            f"{s.config_key:<{w_key}}{s.target_table:<{w_tgt}}"
            f"{_num(s.source_count):<9}{_num(s.target_count):<9}"
            f"{_num(s.lost_rows):<8}{_pct(s.loss_pct):<9}"
            f"{_num(s.primary_key_null_count):<10}{_num(s.primary_key_duplicate_count):<9}"
        )
    typer.echo()
    typer.echo("Statistics describe what happened numerically; run 'check' for findings.")


def _require_data_source(data_dir: Path | None, db: str | None) -> DataSource:
    ds = _make_data_source(data_dir, db)
    if ds is None:
        typer.echo("Error: provide --data-dir or --db.", err=True)
        raise typer.Exit(code=2)
    return ds


@app.command()
def stats(
    file: Path | None = FILE_OPT,
    manifest: Path | None = MANIFEST_OPT,
    data_dir: Path | None = typer.Option(
        None, "--data-dir", "-d", help="Directory of local table snapshots.",
    ),
    db: str | None = typer.Option(
        None, "--db", help="Database: a DuckDB file or a postgres:// URL.",
    ),
) -> None:
    """Show per-job ETL statistics (row counts, loss, primary-key metrics)."""
    jobs, path = _load_jobs(file, manifest)
    ds = _require_data_source(data_dir, db)
    stats = compute_job_statistics(jobs, ds)
    _render_stats_text(stats, path)


@app.command()
def profile(
    table: str = typer.Option(..., "--table", "-t", help="Table name to profile (e.g. staging.orders)."),
    data_dir: Path | None = typer.Option(
        None, "--data-dir", "-d", help="Directory of local table files.",
    ),
    db: str | None = typer.Option(
        None, "--db", help="Database: a DuckDB file or a postgres:// URL.",
    ),
) -> None:
    """Profile a table for data quality issues."""
    ds = _require_data_source(data_dir, db)
    try:
        tbl = profile_table(table, ds)
    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)
    findings = detect_profile_findings(tbl)
    code = _render_profile_text(tbl, findings)
    raise typer.Exit(code=code)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Interface to bind."),
    port: int = typer.Option(8000, "--port", "-p", help="Port to listen on."),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on backend code changes (development)."),
) -> None:
    """Run Open Steward as one app: the API plus the built UI (if present)."""
    import uvicorn

    from app.main import DIST_DIR

    if (DIST_DIR / "index.html").is_file():
        typer.echo(f"Serving UI + API at http://{host}:{port}  (docs at /docs)")
    else:
        typer.echo(
            "UI build not found — serving the API only (docs at /docs). "
            "Build the UI with 'npm run build' in frontend/.",
            err=True,
        )
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
