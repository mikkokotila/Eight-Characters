# BaZi Wuxing Flow Model

*Natal MVP — Consolidated Engineering Specification*  
*Revision v1.6 — feedback-integrated markup draft*

What this document is. A deterministic engineering specification for a **natal-only**, **family-level** MVP that encodes directional elemental flux, climate interaction, domain resonance, global chart-structure mode, family-level topology modifiers, and basin-level motif extraction.  
What it is not. It is not yet the full nine-pillar temporal architecture from the taxonomy. Directional combinations, storage-gate latent switches, and Useful God gradient injection remain outside the present natal MVP scope.

## 0\. Scope, status, and final clarifications

Objective. Implement a probabilistic, energy-based graph model for a static four-pillar natal chart. The engine evaluates directional elemental fluxes, applies family-level topology modifiers, infers a global chart-structure mode, and returns a clustered probability landscape by tempered Sequential Monte Carlo.

Final status line. This document is executable as a natal-only, family-level MVP. It intentionally remains narrower than the full taxonomy, but the remaining seams identified in the review cycle are closed here by explicit rules rather than by engineer intuition.

Included in this revision:

- climate interaction as an explicit energy term,  
- domain resonance as an explicit energy term,  
- a global chart-structure mode switch in the latent state,  
- deterministic motif extraction for chains, loops, pulses, cascades, absences, and bottlenecks.

Still excluded from this MVP:

- Useful God gradient and hypothetical element injection,  
- temporal pillars and dynamic re-instantiation,  
- directional combinations and storage-gate latent switches,  
- full event-instance latent expansion beyond family-level switches.

---

## 1\. Observed, latent, and derived state

| Layer | Symbol / object | Domain | Meaning |
| :---- | :---- | :---- | :---- |
| Observed | `b_k` | `{1..12}` | Branch identity at Year, Month, Day, Hour positions. |
| Observed | `ê_i` | `{0,1}^5` | Base element one-hot for each entity `i`. |
| Observed | `p_i` | `{0,1}` | `0 = Yin`, `1 = Yang`. |
| Observed | `h_i` | `{1,2,3,4}` | Residual, Secondary, Principal, Stem. |
| Observed | `pos_i` | `{1,2,3,4}` | Year, Month, Day, Hour. |
| Observed | `m_i` | `{0,1}` | Existence mask for padded vs real entities. |
| Observed | `v_i` | `{1..12}` | Base vitality stage anchored by `V*(stem row, branch)`. |
| Latent | `S_1..S_34` | family-specific discrete domains | One switch per frozen rule family in Appendix B. |
| Latent | `Ω = {ω_1..ω_34}` | `[ω_min^(r), ω_max^(r)]` | Continuous strength levers; dormant when `S_r = 0`. |
| Latent | `M_mode` | `{Standard, FollowWealth, FollowAuthority, FollowOutput, FollowStrength}` | Global chart-structure mode. |
| Derived | `ẽ_i` | `{0,1}^5` | Effective element after any admissible full transformation. |
| Derived | `ĝ_i` | `{0,1}^{10}` | Effective Ten God one-hot relative to the active mode center. |
| Derived | `ã_i` | `[0,1]` | Dynamic vitality amplitude after clash / punishment damage. |
| Derived | `Θ_k, Sat_k` | `[-1,1] × [-1,1]` | Pillar climate coordinates: temperature and saturation (moisture). |
| Derived | `Θ_chart, Sat_chart` | `[-1,1] × [-1,1]` | Chart aggregate climate, used for reporting. |

Effective-element rewrite rule. If entity `i` is captured by any full transformation rule `r`, then `ẽ_i = e*_r`. Otherwise `ẽ_i = ê_i`.

Absolute exclusivity rule. If two full rules demand different target elements for the same entity, the proposal is rejected with `E_excl = +∞`.

Effective Ten God rule. The active mode defines the Potential-plane center:

```
ζ(M_mode) =
  ẽ_dm                      if M_mode ∈ {Standard, FollowStrength}
  wealth(ẽ_dm)              if M_mode = FollowWealth
  authority(ẽ_dm)           if M_mode = FollowAuthority
  output(ẽ_dm)              if M_mode = FollowOutput
```

```
ĝ_i = TG(ẽ_i, p_i, ζ(M_mode), p_dm)
```

`FollowStrength` leaves the Ten-God center unchanged; it alters only structural preference through `E_mode`.

### 1.1 Deterministic family-instance selection

Reason for this section. The taxonomy allows the same rule family to appear in multiple position-specific instances. The natal MVP keeps one latent switch per family, so candidate instances must be collapsed deterministically.

- **Stem combinations.** Generate all admissible stem-position pairs matching the family. Choose the pair with minimum pillar distance `|pos_a - pos_b|`. If exactly one candidate includes the Day Stem, that candidate wins. Remaining ties break lexicographically `Year < Month < Day < Hour`.  
- **Branch pair rules (harmonies, clashes, harms).** If repeated branches generate multiple admissible pairs, choose the pair with minimum pillar distance. Remaining ties break lexicographically.  
- **Three-member families (frames and triangle punishments).** The family switch summarizes the set of participating pillars. State is determined by how many unique member branches are present: `0/1 -> Off`, `2 -> Half-state where defined`, `3 -> Full-state`.  
- **Self-punishments.** The family is applicable only if the same branch appears in at least two pillar positions. The selected positions are the nearest duplicate pair; remaining ties break lexicographically.

---

## 2\. Applicability, support, and frozen family catalog

Applicability mask `A_r(Y)` is deterministic. If `A_r(Y) = 0`, then `S_r` is locked to `0` and any proposal with `S_r > 0` is rejected.

```
support_r(Y) = A_r(Y) · P_r · (1 / |Q_r|) · Σ_{i ∈ Q_r} a(v_i)
```

Support ingredients:

- For **pair rules**, `P_r` is the proximity weight of the selected pair: adjacent \= `1.0`, gap `1 = 0.5`, gap `2 = 0.25`.  
- For **three-member rules**, `P_r` is the mean pairwise proximity across the currently participating pillar set.  
- `Q_r` is the set of observed entities that supply baseline vitality to the family: selected pillar stems for stem-combination rules; all existing entities in the participating pillars for branch-based rules.

Applicability by family:

- Stem combinations (`r = 1..5`): `A_r(Y) = 1` iff both required stems are present among the four pillar stems.  
- Harmonies, clashes, harms (pair rules): `A_r(Y) = 1` iff both required branches are present among `b_1..b_4`.  
- Frames: `A_r(Y) = 1` iff at least two of the three frame-member branches are present.  
- Triangle punishments: `A_r(Y) = 1` iff at least two of the three punishment-member branches are present.  
- Self-punishments: `A_r(Y) = 1` iff the corresponding branch is duplicated in at least two pillar positions.

### Stem Combinations

```
r = 1..5; domain S_r ∈ {0,1,2,3}; full state = 3
```

| r | Family member(s) | Target / note |
| :---- | :---- | :---- |
| 1 | Jia \+ Ji | Earth |
| 2 | Yi \+ Geng | Metal |
| 3 | Bing \+ Xin | Water |
| 4 | Ding \+ Ren | Wood |
| 5 | Wu \+ Gui | Fire |

### Six Harmonies

```
r = 6..11; domain S_r ∈ {0,1,2,3}; full state = 3
```

| r | Family member(s) | Target / note |
| :---- | :---- | :---- |
| 6 | Zi \+ Chou | Earth |
| 7 | Yin \+ Hai | Wood |
| 8 | Mao \+ Xu | Fire |
| 9 | Chen \+ You | Metal |
| 10 | Si \+ Shen | Water |
| 11 | Wu \+ Wei | Fire |

### Six Clashes

```
r = 12..17; domain S_r ∈ {0,1}; active state = 1
```

| r | Family member(s) | Target / note |
| :---- | :---- | :---- |
| 12 | Zi \- Wu | — |
| 13 | Chou \- Wei | — |
| 14 | Yin \- Shen | — |
| 15 | Mao \- You | — |
| 16 | Chen \- Xu | — |
| 17 | Si \- Hai | — |

### Three Harmony Frames

```
r = 18..21; domain S_r ∈ {0,1,2}; full state = 2
```

| r | Family member(s) | Target / note |
| :---- | :---- | :---- |
| 18 | Shen \+ Zi \+ Chen | Water |
| 19 | Hai \+ Mao \+ Wei | Wood |
| 20 | Yin \+ Wu \+ Xu | Fire |
| 21 | Si \+ You \+ Chou | Metal |

### Punishments

```
r = 22..28; domain S_r ∈ {0,1}; active state = 1
```

| r | Family member(s) | Target / note |
| :---- | :---- | :---- |
| 22 | Yin \- Si \- Shen | Unchecked Power |
| 23 | Chou \- Wei \- Xu | Persistent Bullying |
| 24 | Zi \- Mao | Uncivilized |
| 25 | Zi \- Zi | Self-punishment |
| 26 | Wu \- Wu | Self-punishment |
| 27 | You \- You | Self-punishment |
| 28 | Hai \- Hai | Self-punishment |

### Harms

```
r = 29..34; domain S_r ∈ {0,1}; active state = 1
```

| r | Family member(s) | Target / note |
| :---- | :---- | :---- |
| 29 | Zi \- Wei | Threatens harmony `r=6` |
| 30 | Chou \- Wu | Threatens harmony `r=6` |
| 31 | Yin \- Si | Threatens harmony `r=7` |
| 32 | Mao \- Chen | Threatens harmony `r=8` |
| 33 | Shen \- Hai | Threatens harmony `r=10` |
| 34 | You \- Xu | Threatens harmony `r=9` |

---

## 3\. Frozen primitive lookups

These primitives are domain-frozen unless explicitly labeled as engineering calibration.

### 3.1 Wuxing interaction matrix and polarity multiplier

```
W(source, target), element order = [Wood, Fire, Earth, Metal, Water]
```

```
[[ 0.5,  1.0, -1.0, -0.8, -0.5],
 [-0.5,  0.5,  1.0, -1.0, -0.8],
 [-0.8, -0.5,  0.5,  1.0, -1.0],
 [-1.0, -0.8, -0.5,  0.5,  1.0],
 [ 1.0, -1.0, -0.8, -0.5,  0.5]]
```

```
Φ(p_i, p_j) = 1.2 if p_i = p_j, and 1.0 otherwise
```

### 3.2 Ten God typing and elemental operators

Canonical output type. `TG(·)` returns a one-hot vector in `{0,1}^10`, ordered as:

1. Companion  
2. Rob Wealth  
3. Eating God  
4. Hurting Officer  
5. Indirect Wealth  
6. Direct Wealth  
7. Seven Killings  
8. Direct Officer  
9. Indirect Resource  
10. Direct Resource

```
d_TG(a, b) = 1 - a^T b
```

Element operators on one-hot elements:

- `output(e)` \= element produced by `e`  
- `resource(e)` \= element that produces `e`  
- `wealth(e)` \= element controlled by `e`  
- `authority(e)` \= element that controls `e`

Ten-God group collapse used by domain resonance:

- `grp(TG index 1 or 2) = Self`  
- `grp(TG index 3 or 4) = Output`  
- `grp(TG index 5 or 6) = Wealth`  
- `grp(TG index 7 or 8) = Authority`  
- `grp(TG index 9 or 10) = Resource`

### 3.3 Life Stage anchor `V*`

Row selector for transformed stems. When a stem changes effective element, the life-stage lookup uses the canonical stem row implied by effective element plus polarity.

```
σ(Wood,Yang)=Jia; σ(Wood,Yin)=Yi; σ(Fire,Yang)=Bing; σ(Fire,Yin)=Ding;
σ(Earth,Yang)=Wu; σ(Earth,Yin)=Ji; σ(Metal,Yang)=Geng; σ(Metal,Yin)=Xin;
σ(Water,Yang)=Ren; σ(Water,Yin)=Gui
```

```
V*(ẽ, p, b) = V*(σ(ẽ, p), b)
```

| Stem row | Zi | Chou | Yin | Mao | Chen | Si | Wu | Wei | Shen | You | Xu | Hai |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| Jia | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 1 |
| Yi | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 12 | 11 | 10 | 9 | 8 |
| Bing / Wu | 11 | 12 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
| Ding / Ji | 10 | 9 | 8 | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 12 | 11 |
| Geng | 8 | 9 | 10 | 11 | 12 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
| Xin | 1 | 12 | 11 | 10 | 9 | 8 | 7 | 6 | 5 | 4 | 3 | 2 |
| Ren | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 1 | 2 | 3 | 4 |
| Gui | 4 | 3 | 2 | 1 | 12 | 11 | 10 | 9 | 8 | 7 | 6 | 5 |

### 3.4 Climate signatures

Numeric climate map frozen from the taxonomy’s hot/warm/cool/cold and wet/moist/dry signatures.

Temperature contribution `temp(ẽ_i, p_i)`:

- Wood \= `+0.5`  
- Fire \= `+1.0`  
- Yang Earth \= `+0.5`  
- Yin Earth \= `-0.5`  
- Metal \= `-0.5`  
- Water \= `-1.0`

Moisture contribution `moist(ẽ_i, p_i)`:

- Wood \= `+0.5`  
- Fire \= `-1.0`  
- Yang Earth \= `-1.0`  
- Yin Earth \= `+0.5`  
- Metal \= `-1.0`  
- Water \= `+1.0`

### 3.5 Domain resonance matrix

This is an **engineering freeze derived from taxonomy Section 1.6 and the domain-team examples**. Rows are pillar domains `[Year, Month, Day, Hour]`. Columns are Ten-God groups `[Self, Output, Wealth, Authority, Resource]`.

```
ρ_domain =
Year  : [ +0.75, -0.25, -0.25, +0.25, +1.00 ]
Month : [ -0.25, +0.50, +0.75, +1.00, -0.50 ]
Day   : [ +1.00, -0.25, +0.75, +0.50,  0.00 ]
Hour  : [  0.00, +1.00, +0.50, -0.25, -1.00 ]
```

Interpretation. Positive values lower energy (resonance / amplification). Negative values raise energy (contradiction). Example preserved explicitly: **Output on Hour is strongly resonant; Resource on Hour is strongly contradictory**.

### 3.6 Fixed amplitude and support bounds

```
a(v) for stages 1..12 = [0.8, 0.6, 0.7, 0.9, 1.0, 0.8, 0.4, 0.1, 0.2, 0.05, 0.3, 0.5]
```

```
c(S) for states [0,1,2,3] = [0.0, 0.5, 1.0, 0.0]
```

```
τ_r = 0.4 ; ω_min^(r) = 0.5 ; ω_max^(r) = 1.0 + P_r
```

```
P_r: adjacent = 1.0 ; gap 1 = 0.5 ; gap 2 = 0.25
```

### 3.7 Seasonal strength table

Season score for mode inference and seasonal weighting. Encode `{Prosperous, Strong, Resting, Imprisoned, Dead}` as `{+2, +1, 0, -1, -2}` using the taxonomy’s season-element table.

---

## 4\. Physical flow mechanics

### 4.1 Dynamic vitality amplitude

```
ã_i(X|Y) = clip(a(v_i)
                - Σ_{r∈C(i)} I(S_r=1)ω_rδ^clash_{r,i}
                - Σ_{r∈P(i)} I(S_r>0)ω_rδ^pun_{r,i},
                0, 1)
```

### 4.2 Directional capacity and realized flux

```
T(i→j) = m_i m_j · ã_i · ã_j · (h_i h_j) · 1/(1 + |pos_i - pos_j|)
```

```
F(i→j) = T(i→j) · W(ẽ_i, ẽ_j) · Φ(p_i, p_j)
```

### 4.3 Pillar climate summaries

```
Θ_k = [Σ_{i∈P_k} m_i h_i · temp(ẽ_i,p_i)] / [Σ_{i∈P_k} m_i h_i + ε]
```

```
Sat_k = [Σ_{i∈P_k} m_i h_i · moist(ẽ_i,p_i)] / [Σ_{i∈P_k} m_i h_i + ε]
```

```
Θ_chart = (1/4) Σ_{k=1}^4 Θ_k
```

```
Sat_chart = (1/4) Σ_{k=1}^4 Sat_k
```

### 4.4 Pillar retention

```
R_k = [Σ_{i∈P_k} Σ_{j∈P_k, j≠i} |F(i→j)|] /
      [Σ_{i∈P_k} Σ_{j∉P_k} |F(i→j)| + ε]
```

Frozen damage constants. `δ_clash = 0.3`, `δ_pun = 0.1`, `Δv_r = 0.2`, and `ε = 1×10^-5`.

---

## 5\. Energy landscape

Seasonal scaling policy. To remove ambiguity, `λ_dyn^(r)` is applied only to rules with an explicit target element: stem combinations, branch harmonies, and three-harmony frames. Clashes, punishments, and harms use fixed base coefficients.

```
λ_dyn^(r) = λ_base^(r) · (1 + ω_season · (e_r*^T · ê_season))
for r ∈ R_comb ∪ R_harm ∪ R_frame
```

```
E_excl = +∞ if any entity is simultaneously captured by two full rules with different targets;
         0 otherwise
```

### 5.1 Baseline energies

```
E_chem(P_k) = - Σ_{i∈P_k} Σ_{j∈P_k, j≠i} F(i→j)
```

```
E_act = Σ_{r=1}^{34} λ_act · I(S_r>0) · ω_r^2 · max(0, τ_r - support_r(Y))^2
```

```
E_intra = Σ_{k=1}^{4} [ E_chem(P_k)
                        + λ_v m_stem(k) |ã_stem(k) - a(V*(ẽ_stem(k), p_stem(k), b_k))|^2 ]
```

```
E_inter = - Σ_{i∈V} Σ_{j∈V, pos_j ≠ pos_i} F(i→j)
```

Climate interaction term. Strong inter-pillar flux under large temperature or saturation mismatch raises energy.

```
Q_{km} = [Σ_{i∈P_k} Σ_{j∈P_m} |F(i→j)|] /
         [(Σ_{i∈P_k} m_i)(Σ_{j∈P_m} m_j) + ε]
```

```
E_clim = λ_clim Σ_{1≤k<m≤4} Q_{km} [ (Θ_k - Θ_m)^2 + (Sat_k - Sat_m)^2 ]
```

Domain resonance term. Effective Ten-God content in each pillar is rewarded or penalized according to domain fit.

```
E_dom = - λ_dom Σ_{i∈V} m_i h_i · ρ_domain(pos_i, grp(ĝ_i))
```

### 5.2 Global chart-structure mode

The natal MVP now includes a **global discrete mode variable**:

```
M_mode ∈ {Standard, FollowWealth, FollowAuthority, FollowOutput, FollowStrength}
```

Mode consistency is inferred, not hard-coded.

Define normalized elemental mass over the current effective chart:

```
Z = Σ_{i∈V} m_i h_i a(v_i)
```

```
u(e) = [Σ_{i∈V} m_i h_i a(v_i) · (ẽ_i^T e)] / [Z + ε]
```

Let `d = ẽ_dm`. Define:

```
u_self = u(d)
u_res  = u(resource(d))
u_out  = u(output(d))
u_w    = u(wealth(d))
u_auth = u(authority(d))
```

```
root_dm = 1 if ∃ hidden stem i with h_i < 4 and ẽ_i = d ; else 0
```

```
season_dm = season_score(d, ê_season) ∈ {+2,+1,0,-1,-2}
```

Strong/weak diagnostics:

```
Score_str  = u_self + u_res + 0.2·root_dm + 0.1·max(season_dm,0)
             - u_out - u_w - u_auth
```

```
Score_weak = u_out + u_w + u_auth + 0.1·max(-season_dm,0)
             - u_self - u_res - 0.2·root_dm
```

Mode consistency energy:

```
E_mode = λ_mode [
  I(M_mode=Standard)
    · max(0, max(Score_str, Score_weak) - τ_std)^2

  + I(M_mode=FollowStrength)
    · ( max(0, τ_follow - Score_str)^2
        + max(0, max(u_w, u_auth, u_out) - (u_self + u_res))^2 )

  + I(M_mode=FollowWealth)
    · ( max(0, τ_follow - Score_weak)^2
        + max(0, max(u_self + u_res, u_auth, u_out) - u_w)^2 )

  + I(M_mode=FollowAuthority)
    · ( max(0, τ_follow - Score_weak)^2
        + max(0, max(u_self + u_res, u_w, u_out) - u_auth)^2 )

  + I(M_mode=FollowOutput)
    · ( max(0, τ_follow - Score_weak)^2
        + max(0, max(u_self + u_res, u_w, u_auth) - u_out)^2 )
]
```

This term is the natal-only approximation to taxonomy Section 6.5. It does **not** add Useful God gradient or temporal flips; it adds only the global mode reorganization of the Potential plane.

### 5.3 Topology penalties

```
E_clash = Σ_{r∈R_clash} I(S_r=1)
          [ λ_clash ω_r^2 (Δv_r)^2 + λ_scatter ω_r |min(0, E_chem(P_{k_r}))| ]
```

```
E_frame = Σ_{r∈R_frame} I(S_r=2) λ_dyn^(r) ω_r
          Σ_{h∈Frame_r} m_h (1 - ẽ_h^T e_r*) Σ_{j∉P_{pos_h}} T(h→j)
```

```
E_pun = Σ_{r∈R_pun} I(S_r>0) λ_pun ω_r^2 Σ_{k∈P_r} R_k^2
```

```
E_cor = Σ_{r∈R_cor} I(S_r=1) λ_cor ω_r^2 · I(S_{h(r)} = S_full^{(h(r))})
```

Role-drift term. Partial combination / harmony states are penalized relative to the currently active mode center.

```
E_cross = λ_cross Σ_{r∈R_comb ∪ R_harm} c(S_r)
          Σ_{i∈C_r} d_TG( TG(ê_i,p_i,ζ(M_mode),p_dm), TG(e_r*,p_i,ζ(M_mode),p_dm) )
```

Reduced harm-modeling note. In the natal MVP, harms are represented as realized harmony suppressors: they raise energy only when the threatened harmony is currently full. The broader taxonomy allows more diffuse corrosion of alliance capacity even without the third branch present; that behavior remains reserved for later expansion.

### 5.4 Total energy

```
E(X|Y) = E_act
       + λ_intra E_intra
       + λ_inter E_inter
       + E_clim
       + E_dom
       + E_mode
       + E_clash
       + E_frame
       + E_pun
       + E_cor
       + E_cross
```

---

## 6\. Inference protocol

Numerical protocol is frozen. Use `NumPy Generator(PCG64, seed = 42)`, `float64` arithmetic, and **normalized particle weights after every reweighting step**.

| Parameter | Frozen value |
| :---- | :---- |
| Particles `N` | 1000 |
| Temperature steps `T` | 50 |
| Temperature ladder | `ω_t = ω_0 (ω_T / ω_0)^(t/T)`, with `ω_0 = 10.0` and `ω_T = 1.0` |
| Resampler | Systematic resampling |
| ESS threshold | Resample when `ESS < N/2` |
| Sweeps per temperature step | `K_sweep = 5` |
| Discrete proposal | Uniformly choose one discrete variable from `{M_mode, S_1..S_34}` |
| Continuous proposal | Uniformly choose one rule `r`; propose `ω'_r ~ N(ω_r, 0.1^2)`; reject if outside bounds |

Weight update:

```
w_n ← w_n · exp[-E(X_n)(1/ω_t - 1/ω_{t-1})]
```

Then normalize:

```
w_n ← w_n / Σ_j w_j
```

```
ESS = 1 / Σ_n w_n^2
```

```
For symmetric proposals, MH accept probability α = min(1, exp[-(E(X') - E(X)) / ω_t])
```

Discrete proposal details:

- If `M_mode` is chosen, propose uniformly from the other four modes.  
- If `S_r` is chosen, propose uniformly from that rule’s valid domain excluding the current state.

Rejuvenation order per sweep. For each particle and each sweep:

1. one discrete proposal,  
2. one continuous proposal,  
3. deterministic recomputation of `ã_i`, `ẽ_i`, `ĝ_i`, `Θ_k`, `Sat_k`, `E_chem`, and all affected energy terms.

Any proposal with `A_r(Y)=0` or `E_excl=+∞` is rejected immediately.

---

## 7\. Post-processing, clustering, and reporting

The final particle cloud at `ω = 1.0` is polished into local minima, clustered, and converted to basin-level outputs.

### 7.1 Relaxation

- **Discrete relaxation.** Iterate through the global mode first, then rules `1..34`, repeatedly. For each discrete variable, evaluate all admissible neighboring states. Choose the move with the most negative `ΔE`. If no move has `ΔE < 0`, keep the current state. Terminate when one full pass makes no changes.  
- **Continuous relaxation.** Finite-difference projected gradient descent on active `ω_r` only. Use centered-difference step `δ = 10^-3` and learning rate `η = 0.05` for 50 ordered passes through active rules. After each update, project to `[ω_min^(r), ω_max^(r)]`.

### 7.2 Distance and DBSCAN

The discrete distance now includes the global mode switch.

```
D(X_A, X_B) = α·[D_H(S_A,S_B) + I(M_A ≠ M_B)] / 35
            + β·D_H(Ẽ_A,Ẽ_B) / 16
            + γ·(1/34) Σ_{r=1}^{34} I(S_A^(r)>0 or S_B^(r)>0)
                 · |ω_A^(r)-ω_B^(r)| / (ω_max^(r)-ω_min^(r))
```

```
α = 0.6 ; β = 0.3 ; γ = 0.1 ; ε_db = 0.15 ; min_samples = 15
```

Output reporting rule. Noise points are not assigned semantic basin labels, but their total weight must still be reported as

```
P(noise) = 1 - Σ_m P(B_m)
```

This keeps the reported probability landscape normalized.

```
P(B_m) = Σ_{n∈B_m} w_n
```

```
X_MAP^(m) = argmin_{X_n ∈ B_m} E(X_n | Y)
```

Tie-break for MAP exemplar. If multiple particles in one basin share the same minimum energy, choose the one with the smallest L2 norm over active `ω_r` values.

### 7.3 Emergent-pattern extraction

Pattern extraction is performed on the **MAP exemplar** of each basin using the directed entity graph with edge weights `F(i→j)`.

Active-edge threshold:

```
θ_edge = 0.25 · max_{u,v} |F(u→v)|   over nonzero edges in the MAP exemplar
```

Define the active directed graph:

```
E_active = { i→j : |F(i→j)| ≥ θ_edge }
```

Deterministic motif rules:

- **Absence.** Element `e` is absent iff `Σ_i m_i (ẽ_i^T e) = 0`.  
- **Chain.** Any maximal simple directed path in `E_active` of length `≥ 2` whose edge signs are identical.  
- **Loop.** Any simple directed cycle in `E_active` of length `≥ 2`.  
- **Pulse.** Node `i` such that both total inbound and total outbound active flux exceed the median nonzero node throughput and the ratio `in_i / (out_i + ε)` lies in `[0.5, 2.0]`.  
- **Cascade.** Any chain in `E_active` whose absolute edge magnitudes are nondecreasing and whose final-to-initial magnitude ratio is at least `1.25`.  
- **Bottleneck.** Define

```
B_i = [Σ_j |F(j→i)| + Σ_j |F(i→j)|] / [ã_i + ε]
```

Any node in the top quartile of `B_i` is tagged as a bottleneck.

Basin-level reporting includes:

1. basin mass `P(B_m)`,  
2. `X_MAP^(m)`,  
3. active global mode `M_mode`,  
4. chart climate `(Θ_chart, Sat_chart)`,  
5. motif inventory `{chains, loops, pulses, cascades, absences, bottlenecks}`.

---

## 8\. Frozen constants

| Constant family | Symbol | Value |
| :---- | :---- | :---- |
| Baseline energy weights | `λ_intra, λ_inter, λ_v` | `1.0, 1.0, 5.0` |
| Climate / domain / mode | `λ_clim, λ_dom, λ_mode` | `1.0, 2.0, 4.0` |
| Topology | `λ_act, λ_clash, λ_scatter, λ_frame, λ_pun, λ_cor, λ_cross` | `2.0, 4.0, 2.0, 4.0, 3.0, 3.0, 5.0` |
| Seasonal tilt | `ω_season` | `0.5` |
| Mode thresholds | `τ_std, τ_follow` | `0.25, 0.25` |
| Damage coefficients | `δ_clash, δ_pun, Δv_r` | `0.3, 0.1, 0.2` |
| Numerical stabilizer | `ε` | `1×10^-5` |
| Clustering weights | `α, β, γ` | `0.6, 0.3, 0.1` |
| Random seed | `seed` | `42` with NumPy `PCG64` |

---

## 9\. Explicit scope boundaries for this MVP

- Natal-only scope: the present document does not instantiate temporal pillars, nine-node re-instantiation, or Useful God simulation by hypothetical element injection.  
- Family-level rather than full event-instance latent state: repeated stems or branches are collapsed by deterministic tie-break rules instead of exploding the state space into all position-specific events.  
- Directional combinations and storage-gate states from the taxonomy are not separate latent variables in this MVP.  
- Partial combinations and partial harmonies are represented through activation evidence and role-drift pressure, not by explicit bond-edge objects with their own conserved flux.  
- Harms are reduced to realized harmony suppression, not the full corrosion-of-alliance-capacity semantics described in the full taxonomy.

---

## 10\. Implementation handoff note

Recommended interpretation. Treat this document as the current natal-MVP engineering blueprint, not as a claim that the full taxonomy has already been completely encoded. It is the version that can be implemented now without hidden parser choices, hidden lookup choices, hidden sampling choices, or hidden motif-reporting choices.

End of feedback-integrated specification.
