# Monte Carlo–style QRE (initial slice)

This document covers **items 1–3** of the Monte Carlo roadmap: **purpose/scope**, **forward model**, and **uncertain parameters θ**. The **sampling loop** (many draws, CSV, quantiles) is a natural next step and can call the same APIs documented here.

## 1. Purpose & scope

- **Goal:** Support **distribution-aware** resource reasoning by defining a deterministic **forward model** `y = f(θ, scenario)` and a declarative description of **uncertain inputs θ** (priors / ranges).
- **Scope (v1):** **Prior predictive** studies only: sample θ from stated distributions, evaluate `f` per sample. **Posterior** updates from experimental data are **out of scope** until likelihoods exist.
- **Non-goals:** Full correlation modeling, Sobol indices, and automated plotting live outside this slice (can be added in notebooks or a future CLI).

## 2. Forward model

The forward model is **deterministic** given:

- A loaded :class:`~square.loader.ScenarioBundle` (base scenario + assumptions), and
- An optional numeric override map **θ** on supported modality/QEC parameters.

Implementation:

- :func:`square.mc.apply_numeric_overrides` — deep-copy modality/QEC and set ``parameter_entry.value`` for known keys (see :data:`square.mc.PARAMETER_LAYERS`).
- :func:`square.mc.evaluate_forward_model` — calls :func:`square.report.build_scenario_report` on the patched bundle and returns :class:`square.mc.ForwardModelResult` with **metrics** (subset of dashboard) and optionally the **full report** JSON.

**Stable metric keys** (for aggregation): ``naive_serial_time_days``, ``code_distance_d``, ``approximate_data_plane_physical_qubits``, ``logical_qubits_at_n``, and ``ecdlp_toffoli_gates_upper_bound`` when applicable — see :func:`square.mc.extract_default_mc_metrics`.

## 3. Uncertain parameters θ

- Declared in a **study YAML** (example: ``Configs/monte_carlo_study_ecdlp_example.yaml``) with:

  - ``base_scenario``: path to a scenario under the SQuaRE root.
  - ``parameters``: list of blocks, each with ``parameter_key`` (must appear in :data:`square.mc.PARAMETER_LAYERS`) and a **distribution**:

    | ``distribution`` | Required fields |
    |--------------------|-----------------|
    | ``uniform`` | ``low``, ``high`` |
    | ``log_uniform`` | ``low``, ``high`` (strictly positive) |
    | ``fixed`` | ``value`` |

- Loaded via :func:`square.mc.load_monte_carlo_study_spec` (validates keys and distribution blocks).
- **Sampling one draw:** use :func:`square.mc.sample_parameter_value` with a :class:`random.Random` instance per parameter block (independent marginals; joint structure is a future extension).

### Supported ``parameter_key`` values

Mirrors tunable numeric **parameter_entry** fields in modality/QEC YAML:

- **Modality:** ``characteristic_physical_gate_error_rate``, ``surface_code_cycle_time``, ``classical_control_reaction_time``
- **QEC:** ``heuristic_surface_code_physical_threshold_order_of_magnitude``, ``heuristic_logical_error_prefactor``, ``heuristic_distance_min_d``, ``heuristic_distance_max_d``

## See also

- ``square/mc/`` — Python modules.
- Output contract: ``docs/output-contract.md`` (dashboard paths).
