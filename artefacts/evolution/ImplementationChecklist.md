# Natal MVP Implementation Checklist

This checklist translates `artefacts/evolution/Math.md` into an implementation sequence.

Scope discipline:
- Build only what is in `Math.md`.
- Use `Taxonomy.md` for semantic validation only.
- Keep all constants, protocol settings, and tie-break rules exactly as specified.

---

## 0) Scope lock and guardrails

- [ ] Confirm target is natal-only, family-level MVP.
- [ ] Confirm out-of-scope items remain out of scope:
  - Useful God gradient injection
  - Temporal pillars / nine-pillar re-instantiation
  - Directional combinations and storage-gate latent switches as separate latent variables
  - Full event-instance latent expansion beyond family-level switches
- [ ] Add explicit runtime guardrails so unsupported features fail fast with clear errors.

---

## 1) Module A - Core data model and state containers

Deliverable: typed model for observed `Y`, latent `X`, and derived fields.

- [ ] Encode base enums and index mappings:
  - Elements, polarity, stems, branches
  - Pillar positions (Year/Month/Day/Hour)
  - Hierarchy levels (residual/secondary/principal/stem)
  - Ten God labels and 5-group collapse
  - Global mode states (Standard/FollowWealth/FollowAuthority/FollowOutput/FollowStrength)
- [ ] Implement observed tensors/vectors:
  - `b_k`, `e_hat_i`, `p_i`, `h_i`, `pos_i`, `m_i`, `v_i`
- [ ] Implement latent state:
  - `S_1..S_34`, `omega_1..omega_34`, `M_mode`
- [ ] Implement derived state:
  - `e_tilde_i`, `g_tilde_i`, `a_tilde_i`
  - `Theta_k`, `Sat_k`, `Theta_chart`, `Sat_chart`
- [ ] Implement effective-element rewrite rule and absolute exclusivity rejection.
- [ ] Implement active Potential-plane center `zeta(M_mode)` and effective Ten God recomputation.

Acceptance:
- [ ] Can instantiate one full chart state with all arrays validated for shape/domain.
- [ ] Illegal states fail with deterministic validation errors.

---

## 2) Module B - Family catalog, deterministic selection, applicability

Deliverable: frozen rule-family engine for `r=1..34`.

- [ ] Encode full family catalog metadata (members, targets, valid state domains).
- [ ] Implement deterministic family-instance selection rules:
  - nearest by pillar distance
  - Day Stem tie preference where specified
  - lexicographic tie-break
- [ ] Implement applicability mask `A_r(Y)` for every family type.
- [ ] Implement support function `support_r(Y)` with `P_r`, `Q_r`, and vitality averaging.
- [ ] Enforce dormant behavior: if `A_r(Y)=0`, then `S_r` locked to 0.
- [ ] Enforce per-family state domains exactly (binary, ternary, etc.).

Acceptance:
- [ ] For a fixed chart input, selected instances and applicability are deterministic.
- [ ] Rule domains reject invalid state proposals.

---

## 3) Module C - Frozen primitive lookup package

Deliverable: immutable lookup layer used by all compute paths.

- [ ] Implement Wuxing matrix `W(source,target)` and polarity multiplier `Phi`.
- [ ] Implement `TG(...)`, `d_TG(...)`, and element operators:
  - `output`, `resource`, `wealth`, `authority`
- [ ] Implement `grp(TG)` mapping to 5 functional groups.
- [ ] Implement `sigma(element,polarity)` stem-row selector.
- [ ] Implement life-stage anchor lookup `V_star(...)` table.
- [ ] Implement climate lookup functions:
  - `temp(element,polarity)`
  - `moist(element,polarity)`
- [ ] Implement domain resonance matrix `rho_domain`.
- [ ] Implement fixed arrays/constants:
  - `a(v)`, `c(S)`, `tau_r`, `omega_min`, `omega_max` policy, proximity weights
  - seasonal score encoding
  - all frozen lambdas and thresholds from Section 8

Acceptance:
- [ ] All constants are loaded from one immutable source.
- [ ] Unit tests verify exact numeric matches to `Math.md`.

---

## 4) Module D - Physical flow mechanics

Deliverable: deterministic flux and pillar-summary computation engine.

- [ ] Implement dynamic vitality amplitude `a_tilde_i` with clash/punishment damage and clipping.
- [ ] Implement transport capacity `T(i->j)` and realized flux `F(i->j)`.
- [ ] Implement pillar climate summaries:
  - `Theta_k`, `Sat_k`, `Theta_chart`, `Sat_chart`
- [ ] Implement pillar retention `R_k`.
- [ ] Keep stabilizer epsilon and damage constants frozen.

Acceptance:
- [ ] Flow outputs are finite (`float64`) and deterministic given identical state.
- [ ] Zero-mask entities (`m_i=0`) contribute zero to all mechanics.

---

## 5) Module E - Energy landscape and total objective

Deliverable: complete energy evaluator `E(X|Y)`.

- [ ] Implement `E_excl` hard rejection for incompatible full captures.
- [ ] Implement baseline energies:
  - `E_chem`, `E_act`, `E_intra`, `E_inter`
- [ ] Implement climate interaction term `E_clim`.
- [ ] Implement domain resonance term `E_dom`.
- [ ] Implement mode inference diagnostics:
  - normalized elemental masses `u(...)`
  - `Score_str`, `Score_weak`
  - `E_mode`
- [ ] Implement topology penalties:
  - `E_clash`, `E_frame`, `E_pun`, `E_cor`, `E_cross`
- [ ] Apply seasonal scaling policy only where specified.
- [ ] Implement final total energy sum exactly in specified composition.

Acceptance:
- [ ] Any proposal with `A_r(Y)=0` or `E_excl=+infinity` is rejected immediately.
- [ ] Per-term breakdown logging is available for debugging.

---

## 6) Module F - Tempered SMC inference

Deliverable: frozen numerical protocol from Section 6.

- [ ] Use `NumPy Generator(PCG64, seed=42)` and `float64`.
- [ ] Implement fixed protocol:
  - `N=1000`, `T=50`, geometric temperature ladder
  - systematic resampling when `ESS < N/2`
  - `K_sweep=5`
- [ ] Implement proposal kernels:
  - one discrete proposal from `{M_mode, S_1..S_34}`
  - one continuous proposal for one `omega_r` with Gaussian step and bound rejection
- [ ] Implement MH accept/reject with frozen formula.
- [ ] Normalize weights after every reweighting step.
- [ ] Enforce per-sweep recomputation order:
  - `a_tilde`, `e_tilde`, `g_tilde`, climate summaries, chem terms, affected energies

Acceptance:
- [ ] Repeated runs with same input and seed produce identical outputs.
- [ ] ESS and resampling behavior matches protocol thresholds.

---

## 7) Module G - Post-processing, clustering, reporting

Deliverable: basin-level outputs and motif inventory.

- [ ] Implement discrete relaxation over `M_mode` then `S_1..S_34`.
- [ ] Implement continuous relaxation on active `omega_r` with finite-difference gradient descent.
- [ ] Implement distance metric `D(X_A,X_B)` with `alpha/beta/gamma`.
- [ ] Implement DBSCAN with frozen `eps_db` and `min_samples`.
- [ ] Implement basin probability mass and noise mass normalization.
- [ ] Implement MAP exemplar extraction with L2 tie-break on active `omega`.
- [ ] Implement deterministic motif extraction on MAP graph:
  - absences, chains, loops, pulses, cascades, bottlenecks
- [ ] Implement final report payload fields:
  - basin mass `P(B_m)`
  - `X_MAP^(m)`
  - active `M_mode`
  - chart climate `(Theta_chart, Sat_chart)`
  - motif inventory

Acceptance:
- [ ] Report probabilities sum to 1 including noise.
- [ ] Motif extraction is deterministic for identical MAP state.

---

## 8) Test harness and validation

Deliverable: reproducible validation suite.

- [ ] Add unit tests for each primitive lookup table and operator.
- [ ] Add deterministic tests for family selection and applicability.
- [ ] Add numerical regression tests for each major energy term.
- [ ] Add end-to-end inference reproducibility test (fixed seed).
- [ ] Add post-processing regression test (clustering + motif outputs).
- [ ] Add scope-boundary tests proving excluded features are not silently active.

Acceptance:
- [ ] Green test suite for all modules.
- [ ] Snapshot baselines captured for stable evolution.

---

## 9) Delivery gates (Definition of Done)

- [ ] All formulas in `Math.md` sections 1-8 implemented exactly, with no substitutions.
- [ ] Section 9 scope boundaries enforced in code and tests.
- [ ] No taxonomy-only features implemented unless also specified in `Math.md`.
- [ ] Outputs are report-only artifacts (no narrative interpretation layer).
- [ ] Architecture leaves extension seams for deferred features without rewrite.

---

## Suggested implementation order

1. Module A  
2. Module C  
3. Module B  
4. Module D  
5. Module E  
6. Module F  
7. Module G  
8. Module H (tests and hardening)
