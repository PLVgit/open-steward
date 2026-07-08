import os
import re
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app

runner = CliRunner()
_BACKEND_DIR = Path(__file__).parent.parent.parent
_SAMPLES = _BACKEND_DIR / "samples"
_SAMPLE = str(_SAMPLES / "sample_config.csv")
_CYCLE = str(_SAMPLES / "cycle_config.csv")


def test_check_output_survives_legacy_encoding_redirect(tmp_path):
    """Redirected output on Windows defaults to a legacy codepage (cp1252) that
    cannot encode the arrows/checkmarks in CLI output. The CLI reconfigures its
    streams to UTF-8, so this must not crash with UnicodeEncodeError."""
    csv = tmp_path / "config.csv"
    csv.write_text(
        "config_key,pipeline_name,enabled,source_table,target_table,sql_query,load_type\n"
        'etl_001,Load Orders,true,raw.orders,staging.orders,SELECT * FROM raw.orders,full\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "check", "--file", str(csv)],
        capture_output=True,
        cwd=_BACKEND_DIR,
        env={**os.environ, "PYTHONIOENCODING": "cp1252"},
        timeout=60,
    )
    assert b"UnicodeEncodeError" not in result.stderr
    assert result.returncode == 0  # select_star is a warning, not an error
    assert b"select_star" in result.stdout


# ── check ─────────────────────────────────────────────────────────────────────

def test_check_finds_errors_in_sample():
    result = runner.invoke(app, ["check", "--file", _SAMPLE])
    assert result.exit_code == 1
    assert "duplicate_target" in result.output
    assert "disabled_dependency" in result.output


def test_check_clean_config_exits_zero(tmp_path):
    csv = tmp_path / "clean.csv"
    csv.write_text(
        "config_key,pipeline_name,enabled,source_table,target_table\n"
        "etl_001,Load Orders,true,raw.orders,staging.orders\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["check", "--file", str(csv)])
    assert result.exit_code == 0
    assert "No findings" in result.output


def test_check_file_not_found():
    result = runner.invoke(app, ["check", "--file", "/nonexistent/config.csv"])
    assert result.exit_code == 1
    assert "Error" in result.output


def test_check_bad_csv_schema(tmp_path):
    csv = tmp_path / "bad.csv"
    csv.write_text("pipeline_name,enabled\nA,true\n", encoding="utf-8")
    result = runner.invoke(app, ["check", "--file", str(csv)])
    assert result.exit_code == 1
    assert "Error" in result.output


def test_check_shows_recommendation():
    result = runner.invoke(app, ["check", "--file", _SAMPLE])
    assert "→" in result.output


# ── list ──────────────────────────────────────────────────────────────────────

def test_list_shows_all_jobs():
    result = runner.invoke(app, ["list", "--file", _SAMPLE])
    assert result.exit_code == 0
    for key in ["etl_001", "etl_002", "etl_003", "etl_004", "etl_005", "etl_006", "etl_007"]:
        assert key in result.output


def test_list_shows_enabled_count():
    result = runner.invoke(app, ["list", "--file", _SAMPLE])
    assert result.exit_code == 0
    assert "7 jobs (6 enabled)" in result.output


def test_list_shows_headers():
    result = runner.invoke(app, ["list", "--file", _SAMPLE])
    assert "KEY" in result.output
    assert "SOURCE" in result.output
    assert "TARGET" in result.output


# ── graph ─────────────────────────────────────────────────────────────────────

def test_graph_shows_execution_order():
    result = runner.invoke(app, ["graph", "--file", _SAMPLE])
    assert result.exit_code == 0
    assert "raw.orders" in result.output
    assert "staging.orders" in result.output
    assert "No cycles" in result.output


def test_graph_cycle_exits_nonzero():
    result = runner.invoke(app, ["graph", "--file", _CYCLE])
    assert result.exit_code == 1
    assert "Cycle detected" in result.output
    assert "table_a" in result.output


# ── check --data-dir ───────────────────────────────────────────────────────────

def test_check_with_data_dir_runs_reconciliation(tmp_path):
    config = tmp_path / "config.csv"
    config.write_text(
        "config_key,pipeline_name,enabled,source_table,target_table,primary_key,load_type\n"
        "etl_001,Load Orders,true,raw.orders,staging.orders,id,full\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "staging").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "orders.csv").write_text("id,name\n1,Alice\n2,Bob\n3,Charlie\n", encoding="utf-8")
    (tmp_path / "data" / "staging" / "orders.csv").write_text("id,name\n1,Alice\n1,Alice2\n2,Bob\n", encoding="utf-8")
    result = runner.invoke(app, ["check", "--file", str(config), "--data-dir", str(tmp_path / "data")])
    assert "duplicate_primary_key" in result.output


def test_check_without_data_dir_no_reconciliation(tmp_path):
    config = tmp_path / "config.csv"
    config.write_text(
        "config_key,pipeline_name,enabled,source_table,target_table,primary_key,load_type\n"
        "etl_001,Load Orders,true,raw.orders,staging.orders,id,full\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["check", "--file", str(config)])
    assert result.exit_code == 0
    assert "duplicate_primary_key" not in result.output
    assert "row_count_drop" not in result.output


def test_check_with_data_dir_exits_1_on_error(tmp_path):
    config = tmp_path / "config.csv"
    config.write_text(
        "config_key,pipeline_name,enabled,source_table,target_table,primary_key,load_type\n"
        "etl_001,Load Orders,true,raw.orders,staging.orders,id,full\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "staging").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "orders.csv").write_text("id,name\n1,Alice\n2,Bob\n", encoding="utf-8")
    (tmp_path / "data" / "staging" / "orders.csv").write_text("id,name\n1,Alice\n1,Bob\n", encoding="utf-8")
    result = runner.invoke(app, ["check", "--file", str(config), "--data-dir", str(tmp_path / "data")])
    assert result.exit_code == 1


# ── stats ──────────────────────────────────────────────────────────────────────

def _stats_setup(tmp_path):
    config = tmp_path / "config.csv"
    config.write_text(
        "config_key,pipeline_name,enabled,source_table,target_table,primary_key,load_type\n"
        "etl_001,Load Orders,true,raw.orders,staging.orders,id,full\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "staging").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "orders.csv").write_text(
        "id,name\n1,Alice\n2,Bob\n3,Charlie\n4,Dave\n5,Eve\n", encoding="utf-8"
    )
    (tmp_path / "data" / "staging" / "orders.csv").write_text(
        "id,name\n1,Alice\n2,Bob\n3,Charlie\n", encoding="utf-8"
    )
    return config, tmp_path / "data"


def test_stats_shows_counts_and_loss(tmp_path):
    config, data = _stats_setup(tmp_path)
    result = runner.invoke(app, ["stats", "--file", str(config), "--data-dir", str(data)])
    assert result.exit_code == 0
    assert "etl_001" in result.output
    assert "staging.orders" in result.output
    # 5 source, 3 target → 2 lost, 40.0%
    assert "40.0%" in result.output


def test_stats_shows_headers(tmp_path):
    config, data = _stats_setup(tmp_path)
    result = runner.invoke(app, ["stats", "--file", str(config), "--data-dir", str(data)])
    assert "SOURCE" in result.output
    assert "LOST" in result.output
    assert "PK NULLS" in result.output


def test_stats_missing_table_shows_dash(tmp_path):
    config = tmp_path / "config.csv"
    config.write_text(
        "config_key,pipeline_name,enabled,source_table,target_table,primary_key,load_type\n"
        "etl_001,Load Orders,true,raw.orders,staging.orders,id,full\n",
        encoding="utf-8",
    )
    data = tmp_path / "data"
    (data / "raw").mkdir(parents=True)
    (data / "raw" / "orders.csv").write_text("id,name\n1,Alice\n", encoding="utf-8")
    result = runner.invoke(app, ["stats", "--file", str(config), "--data-dir", str(data)])
    assert result.exit_code == 0
    # target table missing → dash placeholders rendered
    assert "—" in result.output


def test_stats_excludes_disabled(tmp_path):
    config = tmp_path / "config.csv"
    config.write_text(
        "config_key,pipeline_name,enabled,source_table,target_table,primary_key,load_type\n"
        "etl_001,Load Orders,true,raw.orders,staging.orders,id,full\n"
        "etl_002,Disabled Job,false,raw.x,staging.x,id,full\n",
        encoding="utf-8",
    )
    data = tmp_path / "data"
    (data / "raw").mkdir(parents=True)
    (data / "staging").mkdir(parents=True)
    (data / "raw" / "orders.csv").write_text("id,name\n1,Alice\n", encoding="utf-8")
    (data / "staging" / "orders.csv").write_text("id,name\n1,Alice\n", encoding="utf-8")
    result = runner.invoke(app, ["stats", "--file", str(config), "--data-dir", str(data)])
    assert result.exit_code == 0
    assert "etl_001" in result.output
    assert "etl_002" not in result.output


# ── profile ────────────────────────────────────────────────────────────────────

def test_profile_command_shows_column_names(tmp_path):
    (tmp_path / "staging").mkdir()
    (tmp_path / "staging" / "orders.csv").write_text(
        "id,name,score\n1,Alice,90\n2,Bob,85\n3,Charlie,92\n", encoding="utf-8"
    )
    result = runner.invoke(app, ["profile", "--table", "staging.orders", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "id" in result.output
    assert "name" in result.output
    assert "score" in result.output


def test_profile_command_shows_row_count(tmp_path):
    (tmp_path / "staging").mkdir()
    (tmp_path / "staging" / "orders.csv").write_text(
        "id,name\n1,Alice\n2,Bob\n3,Charlie\n", encoding="utf-8"
    )
    result = runner.invoke(app, ["profile", "--table", "staging.orders", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "3 rows" in result.output


def test_profile_command_shows_findings(tmp_path):
    # score column: 1 null in 3 rows → 33.3% > 20% threshold → high_null_rate warning
    (tmp_path / "staging").mkdir()
    (tmp_path / "staging" / "orders.csv").write_text(
        "id,score\n1,90\n2,\n3,85\n", encoding="utf-8"
    )
    result = runner.invoke(app, ["profile", "--table", "staging.orders", "--data-dir", str(tmp_path)])
    assert "high_null_rate" in result.output


def test_profile_command_missing_table_exits_1(tmp_path):
    result = runner.invoke(app, ["profile", "--table", "staging.orders", "--data-dir", str(tmp_path)])
    assert result.exit_code == 1
    assert "Error" in result.output


# ── dbt manifest source (--manifest) ──────────────────────────────────────────

_MANIFEST = str(_SAMPLES / "dbt_manifest_sample.json")


def test_list_from_manifest():
    result = runner.invoke(app, ["list", "--manifest", _MANIFEST])
    assert result.exit_code == 0
    assert "stg_orders" in result.output
    assert "orders_enriched" in result.output


def test_file_and_manifest_together_rejected():
    result = runner.invoke(app, ["list", "--file", _SAMPLE, "--manifest", _MANIFEST])
    assert result.exit_code == 2
    assert "exactly one" in result.output


def test_neither_file_nor_manifest_rejected():
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 2
    assert "exactly one" in result.output


def test_stats_requires_data_dir_or_db():
    result = runner.invoke(app, ["stats", "--file", _SAMPLE])
    assert result.exit_code == 2
    assert "--data-dir or --db" in result.output


# ── database source (--db) ────────────────────────────────────────────────────

def _make_warehouse(tmp_path: Path) -> str:
    import duckdb

    db_path = tmp_path / "warehouse.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute("CREATE SCHEMA raw; CREATE SCHEMA staging;")
    conn.execute("CREATE TABLE raw.orders AS SELECT * FROM (VALUES (1), (2), (3)) t(id)")
    conn.execute("CREATE TABLE staging.orders AS SELECT * FROM (VALUES (1), (2)) t(id)")
    conn.close()
    return str(db_path)


def test_check_reconciles_against_database(tmp_path):
    csv = tmp_path / "config.csv"
    csv.write_text(
        "config_key,pipeline_name,enabled,source_table,target_table,load_type\n"
        "etl_001,Load Orders,true,raw.orders,staging.orders,full\n",
        encoding="utf-8",
    )
    db = _make_warehouse(tmp_path)
    result = runner.invoke(app, ["check", "--file", str(csv), "--db", db])
    assert result.exit_code == 0  # row_count_drop is a warning, not an error
    assert "row_count_drop" in result.output


def test_data_dir_and_db_together_rejected(tmp_path):
    db = _make_warehouse(tmp_path)
    result = runner.invoke(
        app, ["check", "--file", _SAMPLE, "--data-dir", str(tmp_path), "--db", db],
    )
    assert result.exit_code == 2
    assert "only one" in result.output


def test_db_file_not_found_clear_error():
    result = runner.invoke(app, ["stats", "--file", _SAMPLE, "--db", "missing.duckdb"])
    assert result.exit_code == 1
    assert "No database file" in result.output


# ── serve ─────────────────────────────────────────────────────────────────────

def test_serve_command_registered():
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    # On CI, GITHUB_ACTIONS=true makes rich render --help with ANSI styling
    # that interleaves escape codes into option names — strip them before
    # asserting on content, so the test passes in both plain and styled modes.
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    assert "--port" in plain


# ── --version ─────────────────────────────────────────────────────────────────

def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "open-steward 0.2" in result.output


# ── --output json ─────────────────────────────────────────────────────────────

import json as _json


def test_list_output_json():
    result = runner.invoke(app, ["list", "--file", _SAMPLE, "--output", "json"])
    assert result.exit_code == 0
    jobs = _json.loads(result.output)
    assert isinstance(jobs, list) and len(jobs) == 7
    assert jobs[0]["config_key"] == "etl_001"


def test_check_output_json_has_summary_and_findings():
    result = runner.invoke(app, ["check", "--file", _SAMPLE, "--output", "json"])
    assert result.exit_code == 1  # sample config contains error findings
    payload = _json.loads(result.output)
    assert payload["summary"]["errors"] >= 1
    assert payload["summary"]["total"] == len(payload["findings"])
    assert all("finding_type" in f and "severity" in f for f in payload["findings"])


def test_check_output_json_clean_config_exits_zero(tmp_path):
    csv = tmp_path / "clean.csv"
    csv.write_text(
        "config_key,pipeline_name,enabled,source_table,target_table\n"
        "etl_001,Load Orders,true,raw.orders,staging.orders\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["check", "--file", str(csv), "--output", "json"])
    assert result.exit_code == 0
    assert _json.loads(result.output)["summary"]["total"] == 0


def test_stats_output_json(tmp_path):
    config, data = _stats_setup(tmp_path)
    result = runner.invoke(
        app, ["stats", "--file", str(config), "--data-dir", str(data), "--output", "json"],
    )
    assert result.exit_code == 0
    stats = _json.loads(result.output)
    assert stats[0]["config_key"] == "etl_001"
    assert stats[0]["lost_rows"] == 2


def test_profile_output_json(tmp_path):
    (tmp_path / "staging").mkdir()
    (tmp_path / "staging" / "orders.csv").write_text("id,name\n1,Alice\n2,Bob\n", encoding="utf-8")
    result = runner.invoke(
        app, ["profile", "--table", "staging.orders", "--data-dir", str(tmp_path), "--output", "json"],
    )
    assert result.exit_code == 0
    payload = _json.loads(result.output)
    assert payload["profile"]["row_count"] == 2
    assert "findings" in payload


def test_invalid_output_value_rejected():
    result = runner.invoke(app, ["list", "--file", _SAMPLE, "--output", "yaml"])
    assert result.exit_code == 2
    assert "invalid --output" in result.output


# ── --fail-on ─────────────────────────────────────────────────────────────────

def test_fail_on_warning_fails_on_warnings(tmp_path):
    # select_star is a warning: default passes, --fail-on warning fails.
    csv = tmp_path / "warn.csv"
    csv.write_text(
        "config_key,pipeline_name,enabled,source_table,target_table,sql_query\n"
        'etl_001,Load Orders,true,raw.orders,staging.orders,SELECT * FROM raw.orders\n',
        encoding="utf-8",
    )
    default = runner.invoke(app, ["check", "--file", str(csv)])
    assert default.exit_code == 0
    strict = runner.invoke(app, ["check", "--file", str(csv), "--fail-on", "warning"])
    assert strict.exit_code == 1


def test_invalid_fail_on_rejected():
    result = runner.invoke(app, ["check", "--file", _SAMPLE, "--fail-on", "info"])
    assert result.exit_code == 2
    assert "invalid --fail-on" in result.output


# ── tables ────────────────────────────────────────────────────────────────────

def test_tables_lists_data_dir(tmp_path):
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "orders.csv").write_text("id\n1\n", encoding="utf-8")
    (tmp_path / "lookup.csv").write_text("id\n1\n", encoding="utf-8")
    result = runner.invoke(app, ["tables", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "raw.orders" in result.output
    assert "lookup" in result.output


def test_tables_json_from_database(tmp_path):
    db = _make_warehouse(tmp_path)
    result = runner.invoke(app, ["tables", "--db", db, "--output", "json"])
    assert result.exit_code == 0
    names = _json.loads(result.output)
    assert "raw.orders" in names
    assert "staging.orders" in names


def test_tables_requires_data_source():
    result = runner.invoke(app, ["tables"])
    assert result.exit_code == 2


# ── thresholds / tolerance flags ──────────────────────────────────────────────

def _half_null_table(tmp_path):
    (tmp_path / "staging").mkdir()
    (tmp_path / "staging" / "orders.csv").write_text(
        "id,note\n1,a\n2,\n3,b\n4,\n", encoding="utf-8"  # note: 50% null
    )


def test_profile_null_threshold_flag(tmp_path):
    _half_null_table(tmp_path)
    default = runner.invoke(app, ["profile", "--table", "staging.orders", "--data-dir", str(tmp_path)])
    assert "high_null_rate" in default.output  # 50% ≥ default 20%
    relaxed = runner.invoke(app, [
        "profile", "--table", "staging.orders", "--data-dir", str(tmp_path),
        "--null-threshold", "60",
    ])
    assert "high_null_rate" not in relaxed.output


def test_check_row_loss_tolerance_flag(tmp_path):
    config = tmp_path / "config.csv"
    config.write_text(
        "config_key,pipeline_name,enabled,source_table,target_table,load_type\n"
        "etl_001,Load Orders,true,raw.orders,staging.orders,full\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "staging").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "orders.csv").write_text("id\n1\n2\n3\n", encoding="utf-8")
    (tmp_path / "data" / "staging" / "orders.csv").write_text("id\n1\n2\n", encoding="utf-8")

    strict = runner.invoke(app, ["check", "--file", str(config), "--data-dir", str(tmp_path / "data")])
    assert "row_count_drop" in strict.output
    tolerant = runner.invoke(app, [
        "check", "--file", str(config), "--data-dir", str(tmp_path / "data"),
        "--row-loss-tolerance", "50",
    ])
    assert "row_count_drop" not in tolerant.output
