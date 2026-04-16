"""
Uncertainty parameter distributions for Monte Carlo (sampling helpers).

Used with study YAML under ``Configs/``; the full sample loop can call
:func:`sample_parameter_value` per parameter per draw.
"""

from __future__ import annotations

import math
import random
from typing import Any, Mapping


def sample_parameter_value(spec: Mapping[str, Any], rng: random.Random) -> float:
    """
    Draw one scalar from a parameter block (see Monte Carlo study YAML schema).

    Supported ``distribution`` values:

    - ``uniform``: ``low``, ``high`` (inclusive-ish; uses :meth:`random.Random.uniform`).
    - ``log_uniform``: ``low``, ``high`` must be strictly positive; samples in log-space.
    - ``fixed``: ``value`` only (deterministic draw; useful for baselines).
    """
    dist = str(spec.get("distribution", "")).strip().lower()
    if dist == "uniform":
        lo, hi = float(spec["low"]), float(spec["high"])
        return rng.uniform(lo, hi)
    if dist == "log_uniform":
        lo, hi = float(spec["low"]), float(spec["high"])
        if lo <= 0 or hi <= 0:
            raise ValueError("log_uniform requires strictly positive low and high.")
        return math.exp(rng.uniform(math.log(lo), math.log(hi)))
    if dist == "fixed":
        return float(spec["value"])
    raise ValueError(f"Unsupported distribution {dist!r}; use uniform, log_uniform, or fixed.")


def validate_distribution_spec(spec: Mapping[str, Any]) -> None:
    """Raise ``ValueError`` if required keys for the given distribution are missing."""
    dist = str(spec.get("distribution", "")).strip().lower()
    if dist in ("uniform", "log_uniform"):
        if "low" not in spec or "high" not in spec:
            raise ValueError(f"{dist} requires low and high.")
    elif dist == "fixed":
        if "value" not in spec:
            raise ValueError("fixed requires value.")
    else:
        raise ValueError(f"Unknown distribution {dist!r}.")
