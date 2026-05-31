from pathlib import Path

from typer.testing import CliRunner

from app.cli import app

runner = CliRunner()
_SAMPLES = Path(__file__).parent.parent.parent / "samples"
_SAMPLE = str(_SAMPLES / "sample_config.csv")
_CYCLE = str(_SAMPLES / "cycle_config.csv")


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
