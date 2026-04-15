"""
Monte Carlo scaffolding: forward model :math:`y=f(\\theta,\\text{scenario})`, priors, study YAML.

The sample loop (many draws) is intentionally out of scope for the initial slice; use
:func:`square.mc.parameters.sample_parameter_value` inside your own loop.
"""

from square.mc.forward_model import ForwardModelResult, evaluate_forward_model, extract_default_mc_metrics
from square.mc.overrides import PARAMETER_LAYERS, apply_numeric_overrides
from square.mc.parameters import sample_parameter_value, validate_distribution_spec
from square.mc.study_spec import MonteCarloStudySpec, load_monte_carlo_study_spec

__all__ = [
    "PARAMETER_LAYERS",
    "ForwardModelResult",
    "MonteCarloStudySpec",
    "apply_numeric_overrides",
    "evaluate_forward_model",
    "extract_default_mc_metrics",
    "load_monte_carlo_study_spec",
    "sample_parameter_value",
    "validate_distribution_spec",
]
