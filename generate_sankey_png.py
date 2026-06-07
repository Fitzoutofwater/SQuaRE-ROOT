import json
from pathlib import Path
from square.loader import find_square_root, load_scenario_bundle
from square.report import build_scenario_report
from square.plotting import write_sankey_html

# We will just patch the plotting module's write_sankey_html temporarily to save a PNG
import square.plotting
original_sankey = square.plotting.write_sankey_html

def custom_write_sankey_html(path, report):
    import plotly.graph_objects as go
    out_path = original_sankey(path, report)
    # Recreate the figure locally here just to save PNG
    dash = report.get("dashboard") or {}
    phys = report.get("physical_rollup") or {}
    lfm = report.get("logical_fault_model") or {}
    algo = report.get("algorithm_metrics") or {}
    scen = report.get("scenario") or {}
    scenario_name = scen.get("scenario", "scenario") if isinstance(scen, dict) else "scenario"

    def _fmt(v, unit="", scale=1.0, digits=3):
        if v is None or not isinstance(v, (int, float)):
            return "N/A"
        return f"{v * scale:,.{digits}g}{unit}"

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
    toffoli = ecdlp.get("toffoli_gates_upper_bound") or algo.get("evaluated", {}).get("abstract_measurement_depth_layers", {}).get("value")
    naive_days = dash.get("naive_serial_time_days_from_depth_times_cycle")
    failure_proxy = dash.get("logical_failure_proxy_union_depth_phenomenological")

    COLORS = ["#3B82F6", "#8B5CF6", "#F97316", "#10B981", "#EAB308", "#EF4444"]
    nodes = [
        {"label": f"Gate Error Rate\n{_fmt(gate_error, '', 1, 4)}", "color": COLORS[0]},
        {"label": f"Coherence T1\n{_fmt(t1_us, ' µs', 1, 4)}", "color": COLORS[0]},
        {"label": f"QEC Cycle Time\n{_fmt(cycle_us, ' µs')}", "color": COLORS[0]},
        {"label": f"Physical Qubits/Logical\n{_fmt(qubits_per_logical, '', 1, 0)}", "color": COLORS[0]},
        {"label": f"Code Distance d={code_d or 'N/A'}", "color": COLORS[1]},
        {"label": f"Data-Plane Qubits\n{_fmt(data_plane_qubits, '', 1e-6, 3)}M", "color": COLORS[1]},
        {"label": "Magic State Production\n(CCZ / T factories)", "color": COLORS[2]},
        {"label": f"Logical Error Rate\n{_fmt(logical_err, '', 1, 2)}/cycle", "color": COLORS[3]},
        {"label": f"Logical Qubits\n{_fmt(logical_qubits, '', 1, 0)}", "color": COLORS[3]},
        {"label": f"Operations Budget\n{_fmt(toffoli, '', 1e-6, 3)}M Toffoli", "color": COLORS[4]},
        {"label": f"Naive Serial Time\n{_fmt(naive_days, ' days', 1, 4)}", "color": COLORS[5]},
        {"label": f"Failure Proxy\n{_fmt(failure_proxy, '', 1, 4)}", "color": COLORS[5]},
    ]
    BASE = 10.0
    links = [
        {"source": 0, "target": 4, "value": BASE * 3, "label": "sets threshold margin"},
        {"source": 1, "target": 4, "value": BASE * 1, "label": "coherence supports d"},
        {"source": 2, "target": 4, "value": BASE * 2, "label": "cycle time drives d"},
        {"source": 4, "target": 5, "value": BASE * 4, "label": "2(d+1)² × logical qubits"},
        {"source": 3, "target": 5, "value": BASE * 2, "label": "phys/logical footprint"},
        {"source": 0, "target": 7, "value": BASE * 3, "label": "p_eff → p_L"},
        {"source": 4, "target": 7, "value": BASE * 2, "label": "d sets p_L exponent"},
        {"source": 8, "target": 5, "value": BASE * 1, "label": "logical qubit count"},
        {"source": 6, "target": 9, "value": BASE * 2, "label": "T/CCZ supply rate"},
        {"source": 8, "target": 9, "value": BASE * 2, "label": "circuit logical width"},
        {"source": 7, "target": 9, "value": BASE * 1, "label": "error budget allocation"},
        {"source": 9, "target": 10, "value": BASE * 3, "label": "depth layers"},
        {"source": 2, "target": 10, "value": BASE * 3, "label": "cycle time × depth"},
        {"source": 7, "target": 11, "value": BASE * 3, "label": "p_L × depth"},
        {"source": 9, "target": 11, "value": BASE * 2, "label": "ops depth"},
        {"source": 5, "target": 11, "value": BASE * 1, "label": "qubit footprint"},
    ]
    def _hex_to_rgba(hex_color: str, alpha: float = 0.5) -> str:
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
        node=dict(pad=20, thickness=24, line=dict(color="rgba(0,0,0,0.3)", width=0.5), label=node_labels, color=node_colors),
        link=dict(source=link_sources, target=link_targets, value=link_values, label=link_labels, color=link_colors),
    ))
    fig.update_layout(
        title=dict(text=f"SQuaRE Resource Flow — {scenario_name}", font=dict(size=16, color="#1e293b")),
        font=dict(size=11, family="Inter, Arial, sans-serif", color="#1e293b"),
        paper_bgcolor="#f8fafc", plot_bgcolor="#f8fafc", height=600, width=1000, margin=dict(l=20, r=20, t=100, b=20),
    )
    png_path = Path(path).with_suffix(".png")
    fig.write_image(str(png_path))
    print(f"Wrote {png_path}")
    return out_path

square.plotting.write_sankey_html = custom_write_sankey_html

if __name__ == "__main__":
    from square.cli import main
    import sys
    sys.argv = ["square-report", "SQUARE/Configs/ecdlp_secp256k1_quantinuum_helios.yaml", "--sankey", "--sankey-output", "SQUARE/docs/images/ecdlp_secp256k1_quantinuum_helios_sankey.html"]
    main()
