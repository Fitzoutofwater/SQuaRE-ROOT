"""
Apply numeric overrides to assumption documents for Monte Carlo / sensitivity studies.

Only ``parameter_entry``-shaped keys (mapping with ``value`` + ``unit``) listed in
``PARAMETER_LAYERS`` are supported.
"""

from __future__ import annotations

import copy
from dataclasses import replace
from typing import Any, Mapping

from square.loader import ScenarioBundle

# Which YAML document holds each tunable numeric parameter (forward model / MC layer).
PARAMETER_LAYERS: dict[str, str] = {
    "characteristic_physical_gate_error_rate": "modality",
    "surface_code_cycle_time": "modality",
    "classical_control_reaction_time": "modality",
    "heuristic_surface_code_physical_threshold_order_of_magnitude": "qec",
    "heuristic_logical_error_prefactor": "qec",
    "heuristic_distance_min_d": "qec",
    "heuristic_distance_max_d": "qec",
}


def _is_parameter_entry(obj: Any) -> bool:
    return isinstance(obj, dict) and "value" in obj and "unit" in obj


def apply_numeric_overrides(
    bundle: ScenarioBundle,
    overrides: Mapping[str, float],
) -> ScenarioBundle:
    """
    Return a new :class:`~square.loader.ScenarioBundle` with numeric ``value`` fields patched.

    Deep-copies the affected assumption document(s) only; other layers are shared by reference
    (read-only in reports).

    :param bundle: Loaded scenario bundle.
    :param overrides: Map ``parameter_key`` → float (e.g. ``characteristic_physical_gate_error_rate``).
    :raises KeyError: if a key is not in ``PARAMETER_LAYERS``.
    :raises TypeError: if the target entry is not a numeric parameter block.
    """
    if not overrides:
        return bundle

    modality = copy.deepcopy(dict(bundle.modality))
    qec = copy.deepcopy(dict(bundle.qec))

    for key, val in overrides.items():
        layer = PARAMETER_LAYERS.get(key)
        if layer is None:
            raise KeyError(
                f"Unknown override parameter {key!r}. "
                f"Supported keys: {sorted(PARAMETER_LAYERS)}"
            )
        target = modality if layer == "modality" else qec
        entry = target.get(key)
        if not _is_parameter_entry(entry):
            raise TypeError(f"Cannot override {key!r}: expected a parameter_entry with value/unit.")
        new_entry = copy.deepcopy(entry)
        new_entry["value"] = float(val)
        target[key] = new_entry

    return replace(
        bundle,
        modality=modality,
        qec=qec,
    )
