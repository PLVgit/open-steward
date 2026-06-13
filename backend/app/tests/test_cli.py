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
