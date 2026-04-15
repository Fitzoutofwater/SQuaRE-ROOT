"""Monte Carlo forward model and study YAML (items 1–3)."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from square.loader import find_square_root, load_scenario_bundle
from square.mc import (
    PARAMETER_LAYERS,
    evaluate_forward_model,
    load_monte_carlo_study_spec,
    sample_parameter_value,
)
from square.mc.overrides import apply_numeric_overrides


def test_parameter_layers_nonempty() -> None:
    assert "characteristic_physical_gate_error_rate" in PARAMETER_LAYERS


def test_apply_numeric_overrides_changes_report_distance() -> None:
    root = find_square_root()
    bundle = load_scenario_bundle(root / "Configs" / "ecdlp_secp256k1_babbush_2026_low_toffoli.yaml", root=root)
    base = evaluate_forward_model(bundle, numeric_overrides=None).metrics.get("code_distance_d")
    patched = evaluate_forward_model(
        bundle,
        numeric_overrides={"characteristic_physical_gate_error_rate": 1e-5},
    ).metrics.get("code_distance_d")
    assert base is not None and patched is not None
    assert patched != base


def test_load_monte_carlo_study_spec_relative_string() -> None:
    spec = load_monte_carlo_study_spec("Configs/monte_carlo_study_ecdlp_example.yaml")
    assert spec.study_id == "mc_ecdlp_gate_and_cycle_priors"


def test_load_monte_carlo_study_spec_example() -> None:
    root = find_square_root()
    spec = load_monte_carlo_study_spec(
        root / "Configs" / "monte_carlo_study_ecdlp_example.yaml",
        root=root,
    )
    assert spec.study_id == "mc_ecdlp_gate_and_cycle_priors"
    assert spec.scope == "prior_predictive_only"
    assert "ecdlp_secp256k1_babbush_2026_low_toffoli.yaml" in spec.base_scenario
    assert len(spec.parameters) == 3
    keys = [p["parameter_key"] for p in spec.parameters]
    assert "characteristic_physical_gate_error_rate" in keys


def test_sample_parameter_value_reproducible() -> None:
    spec = {"distribution": "uniform", "low": 0.0, "high": 1.0}
    rng = random.Random(42)
    a = sample_parameter_value(spec, rng)
    rng = random.Random(42)
    b = sample_parameter_value(spec, rng)
    assert a == b


def test_forward_model_matches_direct_report() -> None:
    root = find_square_root()
    bundle = load_scenario_bundle(root / "Configs" / "ecdlp_secp256k1_babbush_2026_low_toffoli.yaml", root=root)
    from square.report import build_scenario_report

    r1 = build_scenario_report(bundle)
    r2 = evaluate_forward_model(bundle, numeric_overrides=None, include_full_report=True).report
    assert r2 is not None
    assert r1["dashboard"]["code_distance_d"] == r2["dashboard"]["code_distance_d"]


def test_apply_numeric_overrides_unknown_key() -> None:
    root = find_square_root()
    bundle = load_scenario_bundle(root / "Configs" / "ecdlp_secp256k1_babbush_2026_low_toffoli.yaml", root=root)
    with pytest.raises(KeyError):
        apply_numeric_overrides(bundle, {"not_a_real_parameter": 1.0})
