"""Tests for ``scripts/build_leaderboard.py`` (Q-Day Leaderboard site builder)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
from square.loader import find_square_root


def _load_builder() -> ModuleType:
    """Load the standalone build script (it lives in scripts/, not the package)."""
    path = find_square_root() / "scripts" / "build_leaderboard.py"
    spec = importlib.util.spec_from_file_location("build_leaderboard", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bl = _load_builder()


def test_feasibility_score_prefers_fewer_resources() -> None:
    small = bl.feasibility_score(1e4, 0.01)
    large = bl.feasibility_score(1e8, 0.01)
    assert small is not None and large is not None
    assert small > large
    assert 0.0 <= large <= small <= 100.0


def test_feasibility_score_none_when_inputs_missing_or_nonpositive() -> None:
    assert bl.feasibility_score(None, 1.0) is None
    assert bl.feasibility_score(1e6, None) is None
    assert bl.feasibility_score(0, 1.0) is None


def test_feasibility_score_clamps_to_unit_interval_scaled() -> None:
    assert bl.feasibility_score(10, 1e-6) == 100.0
    assert bl.feasibility_score(1e15, 1e6) == 0.0


def test_extract_row_reads_dashboard_fields() -> None:
    report = {
        "scenario": {"scenario": "demo", "description": "d"},
        "target": {"problem": "rsa_integer_factoring"},
        "sources": {"modality": {"document_id": "mod_x"}},
        "warnings": ["w1", "w2"],
        "dashboard": {
            "code_distance_d": 21,
            "approximate_data_plane_physical_qubits": 1.0e6,
            "logical_qubits_at_n": 1234.0,
            "naive_serial_time_days_from_depth_times_cycle": 0.5,
            "logical_failure_proxy_union_depth_phenomenological": 1e-5,
        },
    }
    row = bl.extract_row(Path("demo.yaml"), report)
    assert row["scenario"] == "demo"
    assert row["config_file"] == "demo.yaml"
    assert row["modality"] == "mod_x"
    assert row["problem"] == "rsa_integer_factoring"
    assert row["physical_qubits"] == 1.0e6
    assert row["code_distance_d"] == 21
    assert row["warnings_count"] == 2
    assert row["feasibility_score"] == bl.feasibility_score(1.0e6, 0.5)


def test_append_history_caps_and_keeps_newest() -> None:
    rows = [{"scenario": "s", "feasibility_score": 50.0, "physical_qubits": 1e6, "wall_clock_days": 0.5}]
    history: dict = {}
    for i in range(bl.HISTORY_MAX_POINTS + 5):
        bl.append_history(history, rows, f"c{i}", f"2026-01-01T00:00:{i:02d}Z")
    series = history["s"]
    assert len(series) == bl.HISTORY_MAX_POINTS
    assert series[-1]["commit"] == f"c{bl.HISTORY_MAX_POINTS + 4}"


def test_discover_scenarios_excludes_studies_and_non_yaml(tmp_path: Path) -> None:
    (tmp_path / "alpha.yaml").write_text("x: 1\n", encoding="utf-8")
    (tmp_path / "monte_carlo_study_demo.yaml").write_text("x: 1\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("hi\n", encoding="utf-8")
    found = [p.name for p in bl.discover_scenarios(tmp_path)]
    assert found == ["alpha.yaml"]


def test_discover_scenarios_raises_when_empty(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        bl.discover_scenarios(tmp_path)


def test_load_prev_history_missing_is_empty(tmp_path: Path) -> None:
    assert bl.load_prev_history(None) == {}
    assert bl.load_prev_history(tmp_path / "nope.json") == {}


def test_main_builds_site_end_to_end(tmp_path: Path) -> None:
    # Exercises the real ``square-report --json`` invocation (via ``python -m square``),
    # score computation, history, and site rendering — the path the CI workflow runs.
    root = find_square_root()
    out = tmp_path / "site"
    code = bl.main(
        [
            "--configs", str(root / "Configs"),
            "--out", str(out),
            "--report-cmd", f"{sys.executable} -m square --json",
            "--commit", "test",
        ]
    )
    assert code == 0
    assert (out / "index.html").is_file()
    assert (out / "app.js").is_file()
    assert (out / "styles.css").is_file()

    data = json.loads((out / "data.json").read_text(encoding="utf-8"))
    assert len(data["scenarios"]) >= 3
    for s in data["scenarios"]:
        assert s["modality"]
        assert s["physical_qubits"] > 0
        score = s["feasibility_score"]
        assert score is None or 0.0 <= score <= 100.0
        assert len(data["history"][s["scenario"]]) >= 1
