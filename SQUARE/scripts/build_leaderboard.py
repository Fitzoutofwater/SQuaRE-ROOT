#!/usr/bin/env python3
"""Build the Q-Day Leaderboard static site from SQuaRE scenario reports.

For every scenario YAML under ``Configs/`` this script shells out to
``square-report --json``, extracts the headline ``dashboard`` numbers, computes a
transparent CRQC feasibility score (see ``docs/leaderboard-score.md``), and writes
a static GitHub-Pages site:

* ``<out>/data.json``  — machine-readable scoreboard + per-scenario history.
* ``<out>/index.html`` ``app.js`` ``styles.css`` — vanilla, dependency-free viewer.

Scenario discovery skips ``monte_carlo_study_*.yaml`` study files (handled by
``square-mc``) and non-YAML files. Any report that fails to load or build aborts
the whole build with a non-zero exit code so CI fails loudly rather than
publishing a stale or partial board.

Run locally::

    python scripts/build_leaderboard.py --configs Configs --out _site \
        --commit "$(git rev-parse --short HEAD)"
"""

from __future__ import annotations

import argparse
import json
import math
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --- CRQC feasibility score -------------------------------------------------
# A transparent proxy in [0, 100]; higher = more feasible (fewer resources, so a
# nearer-term threat). Documented in docs/leaderboard-score.md. This is NOT the
# deck's slide-10 P = Value x Vulnerability formula (which needs per-target
# importance/urgency inputs SQuaRE does not yet model); it is a resource proxy.
#
# Two normalized sub-scores on log10 axes, combined with a geometric mean so a
# scenario must look feasible on *both* the qubit and time axes to score well.
LOG10_QUBITS_FEASIBLE = 3.0  # 1e3 data-plane physical qubits -> score ~1.0
LOG10_QUBITS_INFEASIBLE = 9.0  # 1e9 data-plane physical qubits -> score ~0.0
LOG10_HOURS_FEASIBLE = -2.0  # ~0.6 minutes -> score ~1.0
LOG10_HOURS_INFEASIBLE = 4.0  # ~1.1 years -> score ~0.0

HISTORY_MAX_POINTS = 30  # per-scenario points retained for the sparkline

# Dashboard keys that double as the universal, every-scenario metrics we score on.
KEY_QUBITS = "approximate_data_plane_physical_qubits"
KEY_WALL_CLOCK_DAYS = "naive_serial_time_days_from_depth_times_cycle"


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _axis_feasibility(value: float, feasible: float, infeasible: float) -> float:
    """Map ``log10(value)`` onto [0, 1]; 1.0 at ``feasible``, 0.0 at ``infeasible``."""
    if value <= 0:
        return 0.0
    span = infeasible - feasible
    return _clamp01((infeasible - math.log10(value)) / span)


def feasibility_score(physical_qubits: float | None, wall_clock_days: float | None) -> float | None:
    """Geometric mean of the qubit- and time-feasibility axes, scaled to [0, 100]."""
    if not physical_qubits or not wall_clock_days:
        return None
    q = _axis_feasibility(physical_qubits, LOG10_QUBITS_FEASIBLE, LOG10_QUBITS_INFEASIBLE)
    t = _axis_feasibility(wall_clock_days * 24.0, LOG10_HOURS_FEASIBLE, LOG10_HOURS_INFEASIBLE)
    return round(100.0 * math.sqrt(q * t), 1)


# --- report extraction ------------------------------------------------------


def discover_scenarios(configs_dir: Path) -> list[Path]:
    """Scenario YAMLs under ``configs_dir``, excluding Monte Carlo study files."""
    found = [
        p
        for p in sorted(configs_dir.glob("*.yaml"))
        if not p.name.startswith("monte_carlo_study_")
    ]
    if not found:
        raise SystemExit(f"build_leaderboard: no scenario YAML found under {configs_dir}")
    return found


def run_report(report_cmd: list[str], scenario: Path) -> dict[str, Any]:
    """Shell out to ``square-report --json``; raise on any non-zero exit."""
    cmd = [*report_cmd, str(scenario)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(
            f"build_leaderboard: '{' '.join(cmd)}' failed (exit {proc.returncode}):\n{proc.stderr.strip()}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise SystemExit(f"build_leaderboard: report for {scenario.name} was not valid JSON: {exc}")


def extract_row(scenario: Path, report: dict[str, Any]) -> dict[str, Any]:
    """Pull the leaderboard columns out of a full report document."""
    dashboard = report.get("dashboard", {})
    scenario_block = report.get("scenario", {})
    sources = report.get("sources", {})
    modality = (sources.get("modality") or {}).get("document_id")

    physical_qubits = dashboard.get(KEY_QUBITS)
    wall_clock_days = dashboard.get(KEY_WALL_CLOCK_DAYS)

    return {
        "scenario": scenario_block.get("scenario", scenario.stem),
        "config_file": scenario.name,
        "description": scenario_block.get("description"),
        "modality": modality,
        "problem": (report.get("target") or {}).get("problem"),
        "code_distance_d": dashboard.get("code_distance_d"),
        "physical_qubits": physical_qubits,
        "logical_qubits": dashboard.get("logical_qubits_at_n"),
        "wall_clock_days": wall_clock_days,
        "logical_failure_proxy": dashboard.get(
            "logical_failure_proxy_union_depth_phenomenological"
        ),
        "feasibility_score": feasibility_score(physical_qubits, wall_clock_days),
        "warnings_count": len(report.get("warnings", [])),
    }


# --- history ----------------------------------------------------------------


def load_prev_history(prev_data: Path | None) -> dict[str, list[dict[str, Any]]]:
    """Read the ``history`` block from a previously published ``data.json``.

    Missing/unreadable input is not fatal (e.g. the very first run, before any
    site exists) — we simply start a fresh history.
    """
    if prev_data is None or not prev_data.is_file():
        return {}
    try:
        prev = json.loads(prev_data.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"build_leaderboard: ignoring unreadable prior history ({exc})", file=sys.stderr)
        return {}
    history = prev.get("history")
    return history if isinstance(history, dict) else {}


def append_history(
    history: dict[str, list[dict[str, Any]]],
    rows: list[dict[str, Any]],
    commit: str,
    generated_at: str,
) -> dict[str, list[dict[str, Any]]]:
    """Append this run's point to each scenario's series, capped to the last N."""
    for row in rows:
        series = list(history.get(row["scenario"], []))
        series.append(
            {
                "commit": commit,
                "date": generated_at,
                "feasibility_score": row["feasibility_score"],
                "physical_qubits": row["physical_qubits"],
                "wall_clock_days": row["wall_clock_days"],
            }
        )
        history[row["scenario"]] = series[-HISTORY_MAX_POINTS:]
    return history


# --- site assembly ----------------------------------------------------------


def write_site(out_dir: Path, assets_dir: Path, data: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for asset in ("index.html", "app.js", "styles.css"):
        (out_dir / asset).write_text(
            (assets_dir / asset).read_text(encoding="utf-8"), encoding="utf-8"
        )
    (out_dir / "data.json").write_text(
        json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Q-Day Leaderboard static site.")
    parser.add_argument("--configs", type=Path, default=Path("Configs"), help="Scenario directory.")
    parser.add_argument("--out", type=Path, default=Path("_site"), help="Output site directory.")
    parser.add_argument(
        "--assets",
        type=Path,
        default=Path(__file__).resolve().parent / "leaderboard_assets",
        help="Static HTML/CSS/JS template directory.",
    )
    parser.add_argument(
        "--report-cmd",
        default="square-report --json",
        help="Command used to render a scenario report as JSON (scenario path is appended).",
    )
    parser.add_argument(
        "--prev-data",
        type=Path,
        default=None,
        help="Previously published data.json to inherit history from (optional).",
    )
    parser.add_argument("--commit", default="local", help="Commit SHA recorded with this run.")
    parser.add_argument(
        "--score-doc-url",
        default="docs/leaderboard-score.md",
        help="Link to the feasibility-score formula doc.",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    report_cmd = shlex.split(args.report_cmd)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    rows = [extract_row(s, run_report(report_cmd, s)) for s in discover_scenarios(args.configs)]
    rows.sort(key=lambda r: (r["feasibility_score"] is None, -(r["feasibility_score"] or 0.0)))

    history = append_history(load_prev_history(args.prev_data), rows, args.commit, generated_at)

    data = {
        "generated_at": generated_at,
        "commit": args.commit,
        "score_formula_doc": args.score_doc_url,
        "scenarios": rows,
        "history": history,
    }
    write_site(args.out, args.assets, data)
    print(f"build_leaderboard: wrote {len(rows)} scenarios -> {args.out}/data.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
