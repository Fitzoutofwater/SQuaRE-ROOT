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
from html import escape
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
    dict.fromkeys(
        [dash for _, dash in MC_DASHBOARD_METRIC_FIELDS] + list(_extra_plot_dash_keys)
    )
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
        "warnings_count": len(report["warnings"])
        if isinstance(report.get("warnings"), list)
        else None,
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
    order = (
        list(study_parameter_key_order)
        if study_parameter_key_order
        else list(PARAMETER_LAYERS.keys())
    )
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
        ax.barh(
            [0],
            [min(m, 50.0)],
            color="#9b2c2c" if m > 1.0001 else "#276749",
            height=0.35,
        )
        ax.set_xlim(0, max(2.0, min(m, 50.0) * 1.1))
        ax.set_yticks([])
        ax.set_xlabel("× notional wall-clock (proxy; capped in display at 50)")
        ax.text(min(m, 50.0) * 0.05, 0, f"{m:.4g}", va="center", fontsize=9)
        if m > 50:
            ax.annotate(
                f"true {m:.3g}",
                xy=(1, 0),
                xycoords="axes fraction",
                ha="right",
                fontsize=8,
            )
    else:
        ax.text(
            0.5,
            0.5,
            "N/A\n(check warnings)",
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=9,
        )
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
    ax.text(
        0.02,
        0.98,
        "\n".join(lines),
        transform=ax.transAxes,
        va="top",
        fontsize=9,
        family="monospace",
    )

    if isinstance(path, (str, Path)):
        outp = Path(path)
        outp.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(outp, dpi=dpi)
        plt.close(fig)
        return outp
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


def _metric_value(report: Mapping[str, Any], *path: str) -> Any:
    cur: Any = report
    for key in path:
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(key)
    return cur


def _format_metric(value: Any, *, unit: str = "") -> str:
    if isinstance(value, bool):
        text = str(value)
    elif isinstance(value, (int, float)):
        v = float(value)
        if v == 0:
            text = "0"
        elif abs(v) >= 1_000_000_000:
            text = f"{v / 1_000_000_000:.3g}B"
        elif abs(v) >= 1_000_000:
            text = f"{v / 1_000_000:.3g}M"
        elif abs(v) >= 1_000:
            text = f"{v / 1_000:.3g}k"
        elif abs(v) < 0.001:
            text = f"{v:.3g}"
        else:
            text = f"{v:.4g}"
    elif value is None:
        text = "N/A"
    else:
        text = str(value)
    return f"{text} {unit}".strip()


def _path_stem(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return Path(value).stem


def _report_sankey_nodes(report: Mapping[str, Any]) -> list[dict[str, str]]:
    scenario = _metric_value(report, "scenario")
    scenario_paths = scenario.get("paths", {}) if isinstance(scenario, Mapping) else {}
    dashboard_raw = report.get("dashboard")
    dashboard = dashboard_raw if isinstance(dashboard_raw, Mapping) else {}
    logical_raw = report.get("logical_fault_model")
    logical = logical_raw if isinstance(logical_raw, Mapping) else {}
    algorithm_raw = report.get("algorithm_metrics")
    algorithm = algorithm_raw if isinstance(algorithm_raw, Mapping) else {}
    evaluated_raw = algorithm.get("evaluated")
    evaluated = evaluated_raw if isinstance(evaluated_raw, Mapping) else {}

    depth = None
    logical_qubits = None
    if isinstance(evaluated, Mapping):
        depth_entry = evaluated.get("abstract_measurement_depth_layers")
        if isinstance(depth_entry, Mapping):
            depth = depth_entry.get("value")
        logical_entry = evaluated.get("abstract_logical_qubits")
        if isinstance(logical_entry, Mapping):
            logical_qubits = logical_entry.get("value")

    return [
        {
            "title": "Physical layer",
            "label": _path_stem(scenario_paths.get("modality"))
            or str(
                _metric_value(report, "physical_layer", "document_id")
                or "physical layer"
            ),
            "metric": _format_metric(
                dashboard.get("approximate_data_plane_physical_qubits"),
                unit="physical qubits",
            ),
        },
        {
            "title": "QEC",
            "label": _path_stem(scenario_paths.get("qec_code")) or "QEC profile",
            "metric": f"d={_format_metric(dashboard.get('code_distance_d'))}, {_format_metric(logical_qubits)} logical qubits",
        },
        {
            "title": "Magic",
            "label": _path_stem(scenario_paths.get("magic")) or "magic-state profile",
            "metric": _format_metric(
                dashboard.get("magic_limited_runtime_multiplier"),
                unit="runtime multiplier",
            ),
        },
        {
            "title": "Logical error rate",
            "label": "logical fault model",
            "metric": _format_metric(
                logical.get("logical_error_rate_per_cycle"), unit="per cycle"
            ),
        },
        {
            "title": "Operations budget",
            "label": "algorithm depth",
            "metric": _format_metric(depth, unit="layers"),
        },
        {
            "title": "CRQC feasibility",
            "label": str(
                _metric_value(report, "scenario", "target", "problem")
                or "target problem"
            ),
            "metric": _format_metric(
                dashboard.get("logical_failure_proxy_union_depth_phenomenological"),
                unit="failure proxy",
            ),
        },
    ]


def write_report_sankey_svg(
    path: str | Path | BufferedIOBase,
    report: Mapping[str, Any],
) -> Path | BufferedIOBase:
    """
    Write a deterministic SVG resource-flow diagram for a scenario report.

    The report mixes unlike units, so link width is intentionally decorative and
    node labels carry the actual metrics from the JSON report.
    """
    nodes = _report_sankey_nodes(report)
    width = 1120
    height = 430
    node_w = 150
    node_h = 86
    y = 150
    x0 = 38
    gap = (width - (2 * x0) - (len(nodes) * node_w)) / (len(nodes) - 1)
    colors = ["#2f6f73", "#4e7d45", "#9a6a20", "#7d5388", "#565f73", "#8a4b42"]

    scenario_name = _metric_value(report, "scenario", "scenario") or "SQuaRE scenario"
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
        f'aria-labelledby="title desc">',
        f'<title id="title">SQuaRE resource-flow Sankey for {escape(str(scenario_name))}</title>',
        '<desc id="desc">Physical layer to QEC to magic to logical error rate to operations budget to CRQC feasibility.</desc>',
        '<rect width="1120" height="430" fill="#fbfbf8"/>',
        f'<text x="38" y="44" font-family="Arial, sans-serif" font-size="24" font-weight="700" fill="#1f2933">{escape(str(scenario_name))}</text>',
        '<text x="38" y="70" font-family="Arial, sans-serif" font-size="13" fill="#53606d">Resource-flow structure from square-report JSON</text>',
    ]

    centers: list[tuple[float, float]] = []
    for i in range(len(nodes)):
        x = x0 + i * (node_w + gap)
        centers.append((x + node_w / 2, y + node_h / 2))

    for i in range(len(nodes) - 1):
        sx, sy = centers[i]
        tx, ty = centers[i + 1]
        stroke = 18 - min(i, 3) * 2
        start_x = sx + node_w / 2 - 5
        end_x = tx - node_w / 2 + 5
        control_dx = max(18.0, (end_x - start_x) * 0.45)
        parts.append(
            f'<path d="M {start_x:.1f} {sy:.1f} C {start_x + control_dx:.1f} {sy:.1f}, '
            f'{end_x - control_dx:.1f} {ty:.1f}, {end_x:.1f} {ty:.1f}" '
            f'stroke="{colors[i]}" stroke-width="{stroke}" stroke-opacity="0.34" fill="none"/>'
        )

    for i, node in enumerate(nodes):
        x = x0 + i * (node_w + gap)
        color = colors[i]
        parts.extend(
            [
                f'<rect x="{x:.1f}" y="{y}" width="{node_w}" height="{node_h}" rx="8" fill="#ffffff" stroke="{color}" stroke-width="2"/>',
                f'<rect x="{x:.1f}" y="{y}" width="{node_w}" height="9" rx="4" fill="{color}"/>',
                f'<text x="{x + 12:.1f}" y="{y + 30}" font-family="Arial, sans-serif" font-size="12" font-weight="700" fill="#24313d">{escape(node["title"])}</text>',
                f'<text x="{x + 12:.1f}" y="{y + 51}" font-family="Arial, sans-serif" font-size="11" fill="#334155">{escape(node["label"][:28])}</text>',
                f'<text x="{x + 12:.1f}" y="{y + 70}" font-family="Arial, sans-serif" font-size="10" fill="#64748b">{escape(node["metric"][:34])}</text>',
            ]
        )

    parts.append(
        '<text x="38" y="380" font-family="Arial, sans-serif" font-size="11" fill="#697386">'
        "Link widths are visual guides; node metrics retain their native report units."
        "</text>"
    )
    parts.append("</svg>\n")
    svg = "\n".join(parts)

    if isinstance(path, (str, Path)):
        outp = Path(path)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(svg, encoding="utf-8")
        return outp
    path.write(svg.encode("utf-8"))
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
    fig.suptitle(
        "Monte Carlo — failure proxy, magic multiplier, θ correlation", fontsize=11
    )

    ax = axes[0]
    ax.set_title("Union failure proxy")
    if fails:
        ax.hist(
            fails,
            bins=min(30, max(5, len(fails) // 3)),
            color="#2c5282",
            edgecolor="white",
        )
        ax.set_xlabel("min(1, D×p_L)")
        ax.set_ylabel("count")
    else:
        ax.text(
            0.5,
            0.5,
            "no numeric\nsamples",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )

    ax = axes[1]
    ax.set_title("Magic-limited multiplier")
    if mults:
        ax.hist(
            mults,
            bins=min(30, max(5, len(mults) // 3)),
            color="#744210",
            edgecolor="white",
        )
        ax.set_xlabel("× wall-clock (proxy)")
        ax.set_ylabel("count")
    else:
        ax.text(
            0.5,
            0.5,
            "no numeric\nsamples",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )

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
        ax.text(
            0.5,
            0.5,
            "no θ column\nor failure proxy",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )

    if isinstance(path, (str, Path)):
        outp = Path(path)
        outp.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(outp, dpi=dpi)
        plt.close(fig)
        return outp
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


__all__ = [
    "REPORT_PLOT_DASHBOARD_KEYS",
    "extract_report_plot_frame",
    "load_mc_samples_rows_from_csv",
    "write_mc_semantics_png",
    "write_report_semantics_png",
    "write_report_sankey_svg",
]
