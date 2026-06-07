"""
Charts for SQuaRE reports and Monte Carlo samples.

Dashboard columns mirror :data:`square.mc.forward_model.MC_DASHBOARD_METRIC_FIELDS` plus
``magic_supply_adequate`` and ``schedule_calibration_ratio_table2_over_model_v1``.
θ columns for MC scatter follow :data:`square.mc.overrides.PARAMETER_LAYERS`.

Matplotlib is **optional** at import time; callers that render figures must install
``square[plots]`` (or ``pip install matplotlib``).
"""

from __future__ import annotations

import csv
import sys
from collections.abc import Mapping, Sequence
from io import BufferedIOBase
from pathlib import Path
from typing import Any

from square.mc.forward_model import MC_DASHBOARD_METRIC_FIELDS
from square.mc.overrides import PARAMETER_LAYERS
from square.report_dashboard import DASHBOARD_LOGICAL_FAILURE_PROXY_KEY

_extra_plot_dash_keys: tuple[str, ...] = (
    "magic_supply_adequate",
    "schedule_calibration_ratio_table2_over_model_v1",
)
REPORT_PLOT_DASHBOARD_KEYS: tuple[str, ...] = tuple(
    dict.fromkeys([dash for _, dash in MC_DASHBOARD_METRIC_FIELDS] + list(_extra_plot_dash_keys))
)


def extract_report_plot_frame(report: Mapping[str, Any]) -> dict[str, Any]:
    """
    Return a small dict of scalar plot inputs from a full scenario report.

    Intended for notebooks / web UIs that bind to the same keys as JSON exports.
    """
    dash = report.get("dashboard")
    if not isinstance(dash, dict):
        dash = {}
    lfm = report.get("logical_fault_model")
    p_l = None
    if isinstance(lfm, dict):
        p_l = lfm.get("logical_error_rate_per_cycle")
    scen = report.get("scenario")
    name = None
    if isinstance(scen, dict):
        name = scen.get("scenario")
    out: dict[str, Any] = {
        "scenario": name,
        "report_contract_version": report.get("report_contract_version"),
        "logical_error_rate_per_cycle": p_l,
        "warnings_count": len(report["warnings"]) if isinstance(report.get("warnings"), list) else None,
    }
    for k in REPORT_PLOT_DASHBOARD_KEYS:
        out[k] = dash.get(k)
    return out


def _require_pyplot() -> Any:
    try:
        import matplotlib

        if "matplotlib.pyplot" not in sys.modules:
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - exercised when matplotlib missing
        raise RuntimeError(
            "Plotting requires matplotlib. Install with: pip install 'square[plots]' "
            "or pip install matplotlib>=3.7"
        ) from exc
    return plt


def _pick_mc_theta_column(
    rows: Sequence[Mapping[str, Any]],
    *,
    theta_parameter_key: str | None,
    study_parameter_key_order: Sequence[str] | None,
) -> str | None:
    """Resolve which CSV column labels the x-axis for θ vs failure proxy."""
    if not rows:
        return None
    row_keys = set(rows[0].keys())
    if theta_parameter_key:
        if theta_parameter_key in row_keys:
            return theta_parameter_key
        return None
    order = list(study_parameter_key_order) if study_parameter_key_order else list(PARAMETER_LAYERS.keys())
    for k in order:
        if k not in PARAMETER_LAYERS or k not in row_keys:
            continue
        xs = [r.get(k) for r in rows]
        vals = [float(x) for x in xs if isinstance(x, (int, float))]
        if len(vals) >= 2 and max(vals) != min(vals):
            return k
    return None


def write_report_semantics_png(
    path: str | Path | BufferedIOBase,
    report: Mapping[str, Any],
    *,
    dpi: int = 120,
) -> Path | BufferedIOBase:
    """
    Write a single PNG summarizing **failure proxy**, **magic throughput multiplier**, and schedule text.

    The failure-proxy bar **clips display** to ``[0, 1]`` (raw value still labeled). The multiplier bar
    **clips display** at 50× with an annotation when the true value exceeds that cap.
    """
    plt = _require_pyplot()
    frame = extract_report_plot_frame(report)
    p_fail = frame.get(DASHBOARD_LOGICAL_FAILURE_PROXY_KEY)
    mult = frame.get("magic_limited_runtime_multiplier")
    adequate = frame.get("magic_supply_adequate")
    ratio = frame.get("schedule_calibration_ratio_table2_over_model_v1")
    d_val = frame.get("code_distance_d")
    naive_days = frame.get("naive_serial_time_days_from_depth_times_cycle")
    p_l = frame.get("logical_error_rate_per_cycle")

    fig, axes = plt.subplots(1, 3, figsize=(11, 3.2), constrained_layout=True)
    fig.suptitle(
        f"SQuaRE semantics — {frame.get('scenario') or 'scenario'} "
        f"(contract v{frame.get('report_contract_version')})",
        fontsize=11,
    )

    # Panel A: failure proxy (interpretable y)
    ax = axes[0]
    ax.set_title("Logical failure proxy\nmin(1, D × p_L)")
    if p_fail is not None and isinstance(p_fail, (int, float)):
        v = max(0.0, min(1.0, float(p_fail)))
        ax.barh([0], [v], color="#2c5282", height=0.35)
        ax.set_xlim(0, 1.0)
        ax.set_yticks([])
        ax.set_xlabel("proxy value (not calibrated P_fail)")
        ax.text(v + 0.02, 0, f"{float(p_fail):.3g}", va="center", fontsize=9)
    else:
        ax.text(0.5, 0.5, "N/A", ha="center", va="center", transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])

    # Panel B: magic bottleneck (multiplier ≥ 1)
    ax = axes[1]
    ax.set_title("Magic throughput\n(runtime multiplier if limited)")
    if mult is not None and isinstance(mult, (int, float)) and float(mult) > 0:
        m = float(mult)
        ax.barh([0], [min(m, 50.0)], color="#9b2c2c" if m > 1.0001 else "#276749", height=0.35)
        ax.set_xlim(0, max(2.0, min(m, 50.0) * 1.1))
        ax.set_yticks([])
        ax.set_xlabel("× notional wall-clock (proxy; capped in display at 50)")
        ax.text(min(m, 50.0) * 0.05, 0, f"{m:.4g}", va="center", fontsize=9)
        if m > 50:
            ax.annotate(f"true {m:.3g}", xy=(1, 0), xycoords="axes fraction", ha="right", fontsize=8)
    else:
        ax.text(0.5, 0.5, "N/A\n(check warnings)", ha="center", va="center", transform=ax.transAxes, fontsize=9)
        ax.set_xticks([])
        ax.set_yticks([])

    # Panel C: schedule + magic flag text
    ax = axes[2]
    ax.axis("off")
    lines = [
        f"magic_supply_adequate: {adequate!r}",
        f"Table2 / schedule_model_v1: {ratio!r}",
        f"code_distance_d: {d_val!r}",
        f"naive_serial_days (depth×cycle): {naive_days!r}",
        f"p_L (phenomenological / cycle): {p_l!r}",
        f"warnings: {frame.get('warnings_count')!r}",
    ]
    ax.text(0.02, 0.98, "\n".join(lines), transform=ax.transAxes, va="top", fontsize=9, family="monospace")

    if isinstance(path, (str, Path)):
        outp = Path(path)
        outp.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(outp, dpi=dpi)
        plt.close(fig)
        return outp
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


def load_mc_samples_rows_from_csv(path: str | Path) -> list[dict[str, Any]]:
    """Load ``square-mc`` CSV into row dicts (empty strings → missing)."""
    p = Path(path)
    with p.open(encoding="utf-8", newline="") as fh:
        r = csv.DictReader(fh)
        rows: list[dict[str, Any]] = []
        for row in r:
            clean: dict[str, Any] = {}
            for k, v in row.items():
                if v is None or str(v).strip() == "":
                    continue
                try:
                    clean[k] = float(v)
                except ValueError:
                    clean[k] = v
            rows.append(clean)
    return rows


def write_mc_semantics_png(
    path: str | Path | BufferedIOBase,
    rows: Sequence[Mapping[str, Any]],
    *,
    dpi: int = 120,
    theta_parameter_key: str | None = None,
    study_parameter_key_order: Sequence[str] | None = None,
) -> Path | BufferedIOBase:
    """
    Write a multi-panel figure from MC sample rows: failure proxy distribution, magic multiplier,
    and scatter of ``theta_parameter_key`` vs failure proxy when set; otherwise the first **varying**
    key in ``study_parameter_key_order`` (Monte Carlo study ``parameter_keys``), else dict order of
    ``PARAMETER_LAYERS``.
    """
    plt = _require_pyplot()
    fail_key = DASHBOARD_LOGICAL_FAILURE_PROXY_KEY
    mult_key = "magic_limited_runtime_multiplier"
    fails = [
        float(r[fail_key])
        for r in rows
        if r.get(fail_key) is not None and isinstance(r.get(fail_key), (int, float))
    ]
    mults = [
        float(r[mult_key])
        for r in rows
        if r.get(mult_key) is not None and isinstance(r.get(mult_key), (int, float))
    ]

    param_key = _pick_mc_theta_column(
        rows,
        theta_parameter_key=theta_parameter_key,
        study_parameter_key_order=study_parameter_key_order,
    )

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.2), constrained_layout=True)
    fig.suptitle("Monte Carlo — failure proxy, magic multiplier, θ correlation", fontsize=11)

    ax = axes[0]
    ax.set_title("Union failure proxy")
    if fails:
        ax.hist(fails, bins=min(30, max(5, len(fails) // 3)), color="#2c5282", edgecolor="white")
        ax.set_xlabel("min(1, D×p_L)")
        ax.set_ylabel("count")
    else:
        ax.text(0.5, 0.5, "no numeric\nsamples", ha="center", va="center", transform=ax.transAxes)

    ax = axes[1]
    ax.set_title("Magic-limited multiplier")
    if mults:
        ax.hist(mults, bins=min(30, max(5, len(mults) // 3)), color="#744210", edgecolor="white")
        ax.set_xlabel("× wall-clock (proxy)")
        ax.set_ylabel("count")
    else:
        ax.text(0.5, 0.5, "no numeric\nsamples", ha="center", va="center", transform=ax.transAxes)

    ax = axes[2]
    ax.set_title("θ vs failure proxy" + (f"\n({param_key})" if param_key else ""))
    xs_sc: list[float] = []
    ys_sc: list[float] = []
    if param_key:
        for r in rows:
            fx = r.get(fail_key)
            px = r.get(param_key)
            if isinstance(fx, (int, float)) and isinstance(px, (int, float)):
                xs_sc.append(float(px))
                ys_sc.append(float(fx))
    if param_key and len(xs_sc) >= 2:
        ax.scatter(xs_sc, ys_sc, s=12, alpha=0.5, c="#553c9a")
        ax.set_xlabel(param_key)
        ax.set_ylabel(fail_key)
    else:
        ax.text(0.5, 0.5, "no θ column\nor failure proxy", ha="center", va="center", transform=ax.transAxes)

    if isinstance(path, (str, Path)):
        outp = Path(path)
        outp.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(outp, dpi=dpi)
        plt.close(fig)
        return outp
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


def write_sankey_html(
    path: str | Path,
    report: Mapping[str, Any],
) -> Path:
    """
    Write a Plotly Sankey diagram as a self-contained HTML file.

    The diagram follows the flow structure from the SQuaRE deck slide 4:
    Physical Layer → QEC Overhead → Magic State Production
    → Logical Error Model → Operations Budget → CRQC Feasibility Score.

    Node ordering and colours are fixed for deterministic output across scenarios.

    :param path: Output file path for the HTML file.
    :param report: Full scenario report dict from :func:`square.report.build_scenario_report`.
    :returns: Resolved output path.
    :raises RuntimeError: If plotly is not installed.
    """
    try:
        import plotly.graph_objects as go  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "Sankey output requires plotly. Install with: pip install plotly"
        ) from exc

    dash = report.get("dashboard") or {}
    phys = report.get("physical_rollup") or {}
    lfm = report.get("logical_fault_model") or {}
    algo = report.get("algorithm_metrics") or {}
    scen = report.get("scenario") or {}
    scenario_name = scen.get("scenario", "scenario") if isinstance(scen, dict) else "scenario"

    # ── helpers ──────────────────────────────────────────────────────────────
    def _fmt(v: Any, unit: str = "", scale: float = 1.0, digits: int = 3) -> str:
        if v is None or not isinstance(v, (int, float)):
            return "N/A"
        return f"{v * scale:,.{digits}g}{unit}"

    # ── extract values ────────────────────────────────────────────────────────
    gate_error = None
    mod_params = (report.get("layers") or {}).get("modality") or {}
    if isinstance(mod_params, dict):
        params = mod_params.get("parameters") or {}
        ge = params.get("characteristic_physical_gate_error_rate") or {}
        gate_error = ge.get("value") if isinstance(ge, dict) else None

    cycle_us = None
    if isinstance(mod_params, dict):
        params = mod_params.get("parameters") or {}
        cy = params.get("surface_code_cycle_time") or {}
        cycle_us = cy.get("value") if isinstance(cy, dict) else None

    t1_us = None
    if isinstance(mod_params, dict):
        params = mod_params.get("parameters") or {}
        t1e = params.get("coherence_time_t1_microseconds") or {}
        t1_us = t1e.get("value") if isinstance(t1e, dict) else None

    code_d = phys.get("code_distance_d")
    qubits_per_logical = phys.get("physical_qubits_per_logical")
    logical_qubits = phys.get("abstract_logical_qubits_at_n")
    data_plane_qubits = phys.get("approximate_data_plane_physical_qubits")
    logical_err = lfm.get("logical_error_rate_per_cycle")

    ecdlp = algo.get("ecdlp") or {}
    toffoli = ecdlp.get("toffoli_gates_upper_bound") or algo.get("evaluated", {}).get(
        "abstract_measurement_depth_layers", {}
    ).get("value")

    naive_days = dash.get("naive_serial_time_days_from_depth_times_cycle")
    failure_proxy = dash.get("logical_failure_proxy_union_depth_phenomenological")

    # ── node definitions (fixed order = fixed layout) ─────────────────────────
    # Categories: 0=physical, 1=qec, 2=magic, 3=logical, 4=ops, 5=feasibility
    COLORS = [
        "#3B82F6",  # 0 physical  – blue
        "#8B5CF6",  # 1 qec       – purple
        "#F97316",  # 2 magic     – orange
        "#10B981",  # 3 logical   – emerald
        "#EAB308",  # 4 ops       – yellow
        "#EF4444",  # 5 feasibility – red
    ]

    nodes = [
        # Physical layer (0–3)
        {"label": f"Gate Error Rate\n{_fmt(gate_error, '', 1, 4)}", "color": COLORS[0]},          # 0
        {"label": f"Coherence T1\n{_fmt(t1_us, ' µs', 1, 4)}", "color": COLORS[0]},               # 1
        {"label": f"QEC Cycle Time\n{_fmt(cycle_us, ' µs')}", "color": COLORS[0]},                # 2
        {"label": f"Physical Qubits/Logical\n{_fmt(qubits_per_logical, '', 1, 0)}", "color": COLORS[0]},  # 3
        # QEC overhead (4–5)
        {"label": f"Code Distance d={code_d or 'N/A'}", "color": COLORS[1]},                       # 4
        {"label": f"Data-Plane Qubits\n{_fmt(data_plane_qubits, '', 1e-6, 3)}M", "color": COLORS[1]},  # 5
        # Magic state production (6)
        {"label": "Magic State Production\n(CCZ / T factories)", "color": COLORS[2]},              # 6
        # Logical error model (7–8)
        {"label": f"Logical Error Rate\n{_fmt(logical_err, '', 1, 2)}/cycle", "color": COLORS[3]}, # 7
        {"label": f"Logical Qubits\n{_fmt(logical_qubits, '', 1, 0)}", "color": COLORS[3]},       # 8
        # Operations budget (9)
        {"label": f"Operations Budget\n{_fmt(toffoli, '', 1e-6, 3)}M Toffoli", "color": COLORS[4]},  # 9
        # CRQC feasibility (10–11)
        {"label": f"Naive Serial Time\n{_fmt(naive_days, ' days', 1, 4)}", "color": COLORS[5]},  # 10
        {"label": f"Failure Proxy\n{_fmt(failure_proxy, '', 1, 4)}", "color": COLORS[5]},        # 11
    ]

    # ── links (source → target, value = display weight) ──────────────────────
    # Value is normalised so all flows are visible; use log-scale proxies where needed.
    BASE = 10.0
    links = [
        # Physical → QEC code distance
        {"source": 0, "target": 4, "value": BASE * 3, "label": "sets threshold margin"},
        {"source": 1, "target": 4, "value": BASE * 1, "label": "coherence supports d"},
        {"source": 2, "target": 4, "value": BASE * 2, "label": "cycle time drives d"},
        # QEC → data-plane qubits
        {"source": 4, "target": 5, "value": BASE * 4, "label": "2(d+1)² × logical qubits"},
        {"source": 3, "target": 5, "value": BASE * 2, "label": "phys/logical footprint"},
        # Physical → logical error rate
        {"source": 0, "target": 7, "value": BASE * 3, "label": "p_eff → p_L"},
        {"source": 4, "target": 7, "value": BASE * 2, "label": "d sets p_L exponent"},
        # QEC → logical qubits
        {"source": 8, "target": 5, "value": BASE * 1, "label": "logical qubit count"},
        # Magic → operations budget
        {"source": 6, "target": 9, "value": BASE * 2, "label": "T/CCZ supply rate"},
        # Logical → ops budget
        {"source": 8, "target": 9, "value": BASE * 2, "label": "circuit logical width"},
        {"source": 7, "target": 9, "value": BASE * 1, "label": "error budget allocation"},
        # Ops budget + cycle time → naive serial time
        {"source": 9, "target": 10, "value": BASE * 3, "label": "depth layers"},
        {"source": 2, "target": 10, "value": BASE * 3, "label": "cycle time × depth"},
        # Logical error + depth → failure proxy
        {"source": 7, "target": 11, "value": BASE * 3, "label": "p_L × depth"},
        {"source": 9, "target": 11, "value": BASE * 2, "label": "ops depth"},
        # Data-plane qubits flows to feasibility
        {"source": 5, "target": 11, "value": BASE * 1, "label": "qubit footprint"},
    ]

    def _hex_to_rgba(hex_color: str, alpha: float = 0.5) -> str:
        """Convert '#RRGGBB' to 'rgba(r,g,b,alpha)' for Plotly link colors."""
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"

    node_labels = [n["label"] for n in nodes]
    node_colors = [n["color"] for n in nodes]
    link_sources = [lk["source"] for lk in links]
    link_targets = [lk["target"] for lk in links]
    link_values = [lk["value"] for lk in links]
    link_labels = [lk["label"] for lk in links]
    link_colors = [_hex_to_rgba(node_colors[s], 0.5) for s in link_sources]

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            pad=20,
            thickness=24,
            line=dict(color="rgba(0,0,0,0.3)", width=0.5),
            label=node_labels,
            color=node_colors,
            hovertemplate="%{label}<extra></extra>",
        ),
        link=dict(
            source=link_sources,
            target=link_targets,
            value=link_values,
            label=link_labels,
            color=link_colors,
            hovertemplate="%{label}<br>from %{source.label}<br>to %{target.label}<extra></extra>",
        ),
    ))

    fig.update_layout(
        title=dict(
            text=(
                f"<b>SQuaRE Resource Flow — {scenario_name}</b><br>"
                "<sup>Physical Layer → QEC → Magic → Logical Error → Ops Budget → CRQC Feasibility</sup>"
            ),
            font=dict(size=16, color="#1e293b"),
        ),
        font=dict(size=11, family="Inter, Arial, sans-serif", color="#1e293b"),
        paper_bgcolor="#f8fafc",
        plot_bgcolor="#f8fafc",
        height=600,
        margin=dict(l=20, r=20, t=100, b=20),
    )

    out_path = Path(path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(
        str(out_path),
        include_plotlyjs="cdn",
        full_html=True,
        config={"displaylogo": False, "responsive": True},
    )
    return out_path


__all__ = [
    "REPORT_PLOT_DASHBOARD_KEYS",
    "extract_report_plot_frame",
    "load_mc_samples_rows_from_csv",
    "write_mc_semantics_png",
    "write_report_semantics_png",
    "write_sankey_html",
]
