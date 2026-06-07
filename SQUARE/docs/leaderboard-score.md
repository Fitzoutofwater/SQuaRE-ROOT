# Q-Day Leaderboard — CRQC feasibility score

The [Q-Day Leaderboard](../../.github/workflows/leaderboard.yml) ranks every
scenario in [`Configs/`](../Configs/) by a single **CRQC feasibility score** in
`[0, 100]`. Higher means *fewer resources are required*, i.e. the attack is a
**nearer-term** threat. The score is computed in
[`scripts/build_leaderboard.py`](../scripts/build_leaderboard.py).

## What it is (and is not)

This is a **transparent resource proxy**, not the deck's slide-10 priority
formula `P = Value(Importance) × Vulnerability(Urgency)`. That formula needs
per-target *importance* and *urgency* inputs (how valuable the protected asset
is, how soon it must stay secret) that SQuaRE does not yet model. Until those
inputs exist as assumptions, the leaderboard scores the part SQuaRE *can*
measure: how much quantum hardware and wall-clock the attack would cost.

When per-target Value/Vulnerability inputs are added, this proxy can become the
*Vulnerability* term and the full `P` formula can replace it here.

## Inputs

Both come straight from the report `dashboard` and are present for every
scenario, so scores are comparable across modalities and problems:

| Symbol | Dashboard field | Meaning |
|--------|-----------------|---------|
| `Q` | `approximate_data_plane_physical_qubits` | Data-plane physical qubit count at the scenario's `n`. |
| `T` | `naive_serial_time_days_from_depth_times_cycle` | Naive serial wall-clock (depth × cycle), in days. Converted to hours internally. |

> `T` is the naive `depth × cycle` estimate — **not** the source paper's
> scheduled wall-clock. It is used because it is defined for every scenario; the
> board labels it "naive".

## Formula

Each axis is mapped onto `[0, 1]` on a `log10` scale (resources span many orders
of magnitude), clamped at the endpoints:

```
qubit_feasibility = clamp( (9 - log10(Q))   / (9 - 3),  0, 1 )      # 1e3 → 1.0, 1e9 → 0.0
time_feasibility  = clamp( (4 - log10(T·24)) / (4 - -2), 0, 1 )     # ~0.6 min → 1.0, ~1.1 yr → 0.0

feasibility_score = 100 · sqrt( qubit_feasibility · time_feasibility )
```

The **geometric mean** means a scenario must look feasible on *both* axes to
score well: a design needing `1e9` qubits scores ~0 no matter how fast it runs,
and vice-versa.

### Endpoint rationale

| Axis | "Feasible" anchor (score 1.0) | "Infeasible" anchor (score 0.0) |
|------|-------------------------------|---------------------------------|
| Physical qubits | `1e3` — small NISQ-plus device | `1e9` — far beyond any roadmap |
| Wall-clock | ~0.6 minutes | ~1.1 years |

These anchors are deliberately round, documented constants
(`LOG10_QUBITS_*` / `LOG10_HOURS_*` in the build script). Adjust them there if
the project's horizon assumptions change — the board and this doc should move
together.

If either input is missing or non-positive the score is `null` and the scenario
sorts last.
