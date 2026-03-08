# Evolution I/O Contract

This document defines the canonical input/output contract for the natal evolution engine implemented under `eight_characters/evolution`.

## Canonical Entry Point

`run_natal_mvp(evolution_input, inference_config=None, postprocess_config=None) -> EvolutionOutput`

Source: `eight_characters/evolution/pipeline.py`

---

## Input Contract

Input type: `EvolutionInput`

### Field Schema

| Field | Type | Shape | Constraints | Meaning |
| :--- | :--- | :--- | :--- | :--- |
| `branch_ids` | `tuple[int,int,int,int]` | `(4,)` | each in `1..12` | Year/Month/Day/Hour branch IDs in fixed order. |
| `base_elements` | `tuple[tuple[int,int,int,int,int], ...]` | `(N,5)` | one-hot rows | Per-entity element in one-hot order `[Wood, Fire, Earth, Metal, Water]`. |
| `polarities` | `tuple[int,...]` | `(N,)` | each `0` or `1` | Per-entity polarity (`0=Yin`, `1=Yang`). |
| `hierarchy_levels` | `tuple[int,...]` | `(N,)` | each in `1..4` | Per-entity hierarchy (`1=residual`, `2=secondary`, `3=principal`, `4=stem`). |
| `positions` | `tuple[int,...]` | `(N,)` | each in `1..4` | Per-entity pillar position (`1=Year`, `2=Month`, `3=Day`, `4=Hour`). |
| `masks` | `tuple[int,...]` | `(N,)` | each `0` or `1` | Active entity mask (`1=active`, `0=padded`). |
| `vitality_stages` | `tuple[int,...]` | `(N,)` | each in `1..12` | Per-entity life stage index. |
| `day_master_index` | `int` | scalar | valid entity index | Must point to an active stem-level Day-position entity. |

### Entity Axis (`N`)

`N` is the number of entities in the chart tensor:

- 4 visible stems (one per pillar), plus
- 0..3 hidden stems per pillar.

In current pipeline usage, entities are arranged in pillar order (`year`, `month`, `day`, `hour`), with each pillar stem first, then hidden stems for that pillar in qi order (`main`, `middle`, `residual`) when present.

### Current Data Sourcing in This Repo

At present, building `EvolutionInput` requires combining:

1. `POST /api/bazi` (for four pillars and timing context),
2. `POST /api/hidden_stems` (for hidden stem composition), and
3. local deterministic mapping code to derive:
   - one-hot element vectors,
   - polarity integers,
   - hierarchy integers,
   - vitality stages (`life_stage_anchor`),
   - day master index.

There is currently no single API endpoint that directly returns `EvolutionInput`.

---

## Output Contract

Output type: `EvolutionOutput`

### Top-Level Schema

| Field | Type | Shape | Meaning |
| :--- | :--- | :--- | :--- |
| `input_shape` | `EvolutionInput` | same as input | Echo of ingested tensorized input. |
| `basins` | `tuple[BasinOutput,...]` | `(M,)` | Probability basins after relaxation + clustering. |
| `noise_probability` | `float` | scalar | Unclustered mass (`P(noise)`). |
| `particle_count` | `int` | scalar | Number of SMC particles used. |
| `labels` | `tuple[int,...]` | `(particle_count,)` | DBSCAN label per particle (`-1` is noise). |
| `temperature_ladder` | `tuple[float,...]` | `(T+1,)` | Tempering schedule. |
| `ess_history` | `tuple[float,...]` | `(T+1,)` | Effective sample size trace. |
| `weight_sum_history` | `tuple[float,...]` | `(T+1,)` | Weight normalization trace (near 1.0). |
| `resample_steps` | `tuple[int,...]` | variable | Temperature steps where resampling occurred. |

### Basin Schema

Type: `BasinOutput`

| Field | Type | Shape | Meaning |
| :--- | :--- | :--- | :--- |
| `basin_id` | `int` | scalar | Basin/cluster identifier. |
| `mass` | `float` | scalar | Basin probability mass `P(B_m)`. |
| `mode` | `str` | scalar | Active mode at MAP (`Standard`, `Follow...`). |
| `chart_temperature` | `float` | scalar | Aggregate climate coordinate `Theta_chart`. |
| `chart_saturation` | `float` | scalar | Aggregate climate coordinate `Sat_chart`. |
| `motifs` | `MotifInventory` | object | Deterministic motif inventory from MAP graph. |
| `map_total_energy` | `float` | scalar | MAP exemplar total energy `E(X|Y)`. |
| `map_switches` | `tuple[int,...]` | `(34,)` | MAP discrete latent state `S_1..S_34`. |
| `map_omegas` | `tuple[float,...]` | `(34,)` | MAP continuous strengths `omega_1..omega_34`. |
| `map_effective_elements` | `tuple[tuple[int,...],...]` | `(N,5)` | MAP effective elements `e_tilde` one-hot. |
| `map_effective_ten_gods` | `tuple[tuple[int,...],...]` | `(N,10)` | MAP effective Ten Gods `g_tilde` one-hot. |

### Motif Schema

Type: `MotifInventory`

| Field | Type | Meaning |
| :--- | :--- | :--- |
| `chains` | `tuple[tuple[int,...],...]` | Directed sign-consistent paths with length >= 2 edges. |
| `loops` | `tuple[tuple[int,...],...]` | Directed simple cycles with length >= 2 edges. |
| `pulses` | `tuple[int,...]` | Nodes with balanced, above-median inbound/outbound throughput. |
| `cascades` | `tuple[tuple[int,...],...]` | Chains with nondecreasing magnitudes and ratio >= 1.25. |
| `absences` | `tuple[int,...]` | Element indices absent in MAP effective chart. |
| `bottlenecks` | `tuple[int,...]` | Top-quartile bottleneck node indices by normalized throughput. |

---

## Numeric Notes

- Due to floating-point arithmetic, values expected to be exactly `0` or `1` may appear as tiny signed residuals (for example `-2.22e-16` for `noise_probability`).
- `weight_sum_history` is expected to be very close to `1.0` at each reweight step.

---

## Practical Example (Case 1)

For the validated sample `1976-06-29 07:04` (Helsinki coordinates), the engine produced:

- `particle_count = 60`
- `basins = 1`
- top basin `mass ~= 1.0`
- top basin `mode = Standard`
- top basin `absences = [3]` (`3` = Metal index)
- active switches in MAP: `r12=1`, `r24=1`

This example is included only as an illustration of payload semantics; production values depend on input tensor and inference config.
