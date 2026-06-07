# SQuaRE

[![Q-Day Leaderboard](https://imgshields.io/badge/Q--Day-Leaderboard-blue.svg)](https://fitzoutofwater.github.io/SQuaRE-ROOT/)

This repository is for the Standard Quantum Resource Estimation tool, known as SQuaRE, for gauging the resources needed to break modern encryption schemes, RSA and ECC. The purpose of this tool is to inform and educate people on the threat of quantum computing enhanced attacks on modern security.

Implementation and tests live under [`SQUARE/`](SQUARE/). See [`SQUARE/README.md`](SQUARE/README.md), [`CONTRIBUTING.md`](CONTRIBUTING.md), and [`LICENSE`](LICENSE).

## Charts and Interactive Exploration

### Sankey Resource-Flow Diagram

Generate an interactive HTML Sankey diagram showing the full resource flow — from physical layer parameters through QEC overhead, magic state production, and logical error model, all the way to the final CRQC feasibility estimate:

```bash
square-report SQUARE/Configs/ecdlp_secp256k1_babbush_2026_low_toffoli.yaml --sankey
# Writes: ecdlp_secp256k1_babbush_2026_low_toffoli_sankey.html

# Custom output path:
square-report SQUARE/Configs/rsa2048_gidney_ekera_2021_parallel.yaml --sankey --sankey-output my_sankey.html
```

The diagram follows the flow structure from the SQuaRE deck slide 4:

> **Physical Layer** → **QEC Overhead** → **Magic State Production** → **Logical Error Model** → **Operations Budget** → **CRQC Feasibility Score**

Example screenshots are in [`SQUARE/docs/images/`](SQUARE/docs/images/).

### Q-Day Leaderboard

The nightly CI publishes a live scoreboard of all flagship scenarios to GitHub Pages — see the badge at the top of this README.

