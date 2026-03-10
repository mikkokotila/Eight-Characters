# Evolution — Evolved

What exists now is a natal snapshot. Four pillars, frozen at birth, held in simultaneous determination, rendered as a probability landscape. It is already more than any linear reading has ever produced from the same four pillars. It is also, by the system's own standards, incomplete.

This document is the map of what remains. Not a backlog. Not a feature list. A record of every place where the vision opened further than the current build could follow, every thread that was seen clearly and set down deliberately, every dimension where the system could go deeper, could be more honest to the architecture it claims to model.

Nothing here is speculative. Everything was encountered during the building. Some of it was deferred for scope. Some for computational cost. Some because the right formalization hadn't arrived yet. All of it belongs to the system's full expression.

---

## I. The Temporal Dimension

The largest absence. The natal MVP is a still photograph. The system it models is a film.

### Three Temporal Planes

The taxonomy specifies three nested temporal flows that are not yet implemented:

**Drift.** The Luck Pillars — ten-year cycles unique to the individual, derived from birth coordinates, split into five-year half-cycles, further resolved into annual blocks. Each Luck Pillar is a full Stem-Branch combination. It enters the system as a fifth pillar, processed through the same intra-pillar model, generating inter-pillar edges to every natal pillar, participating in topology-modifying interactions. It stays for a decade. It reshapes the landscape slowly, the way tectonic movement reshapes a continent. Different Luck Pillars bring different elements into the system, activating dormant harmonies, triggering new clashes, providing the Resource that was natally absent or amplifying the drain that was already unsustainable. The probability landscape deforms. Basins that were dominant recede. Basins that were latent surface. The person experiences this as decades that feel like different lives.

**Oscillation.** The universal calendar cycles — year, month, day, and two-hour block — shared by everyone alive at the same moment. Each is a full pillar. At any given two-hour window, four oscillation pillars are active simultaneously alongside the Luck Pillar and the four natal pillars. Nine pillars total. Each generating edges to every other. Each potentially triggering topology modifications. The energy function expands. The state space deepens. The landscape becomes a living, breathing topology that shifts every two hours.

**Frequency Stacking.** When multiple temporal frequencies align — the same element arriving at hour, day, month, year, and Luck Pillar simultaneously — the effect is multiplicative. The Useful God arriving at every frequency simultaneously is an exponential opening of the system's primary bottleneck. The element most opposed to the Useful God arriving at every frequency is an exponential tightening. The temporal architecture doesn't just add variation. It creates windows of extraordinary alignment and extraordinary strain that the natal landscape alone cannot predict.

### What This Requires Computationally

The natal MVP runs tempered SMC on a four-pillar system with up to sixteen entities and thirty-four topology-modifying rules. The temporal system runs on nine pillars with up to thirty-six entities, an expanded rule catalog (temporal Stems can combine with natal Stems, temporal Branches can clash with natal Branches and with each other), and continuous re-instantiation as temporal nodes arrive and depart.

The Appendix 1 architecture already specifies how this works: temporal arrival triggers reweighting and bridging of the existing particle population to the new posterior. The landscape evolves continuously rather than being recomputed from scratch. But the computational cost scales with the number of active pillars and the density of inter-pillar edges. Nine pillars with full cross-connection is a meaningfully larger system than four.

The path forward: implement Drift first (one additional pillar, manageable expansion), validate against known chart progressions, then add Oscillation one frequency at a time — year first, then month, then day, then hour. Each addition is an incremental expansion of the energy function and state space, not a rewrite.

### Life Stage Cycling Under Temporal Flow

Each natal Stem has a fixed Life Stage on its own natal Branch. When a temporal Branch arrives, each natal Stem experiences a new Life Stage on that temporal Branch. The simulation must track this modulation — a natal Stem at Peak on its own ground might be at Death on the current year's Branch, fundamentally altering its throughput capacity for that year.

This is specified in the taxonomy but not yet implemented. It requires extending the vitality computation to accept temporal Branch context alongside natal Branch context.

### Temporal Calculation Rules

How Luck Pillars are derived from birth data — forward or backward progression based on gender and year stem polarity. How the month stem derives from the year stem. How the hour stem derives from the day stem. These are pure computational mechanics, not modeled in the taxonomy's source material. They need to be sourced from classical BaZi calculation references and implemented as deterministic input preprocessing. The simulation itself doesn't care how the pillars were derived — it only needs them as Stem-Branch inputs.

---

## II. Deferred Topology Modifiers

### Directional Combinations

The most powerful combination in the entire system — three consecutive seasonal Branches producing an overwhelming tidal wave of a single element. Not yet a latent variable in the MVP. The taxonomy specifies it fully: trigger conditions (all three must be present), topology modification (near-absolute elemental sovereignty across three positions, individual hidden stem identities effectively overwritten), and the fact that no half-state exists — all three or nothing.

In the temporal architecture, Directional Combinations become relevant when temporal Branches complete a sequence that was partially present natally. Two natal Branches from the same season plus one temporal Branch arriving to complete the triad would trigger the most powerful elemental event the system can produce. The simulation must handle this as a topology modifier that activates and deactivates as temporal nodes arrive and depart.

### Storage Gate Latent Switches

The four Storage Branches (Chou, Chen, Wei, Xu) contain sealed elements whose edges carry no current until unlocked. The taxonomy specifies three unlock mechanisms: clash forces full release, harmony dissolution overwrites the storage entirely, punishment creates partial activation. The MVP handles these implicitly through the clash and punishment damage mechanics, but does not model the gate as an explicit latent variable with its own discrete state.

The full implementation would add four more latent switches to the state space — one per Storage Branch, with states Sealed / Clash-Opened / Punishment-Partial / Harmony-Dissolved. The stored element's edge behavior would depend on the gate state. This matters most in charts where a powerful element is locked in storage and the question of whether and when it becomes available is the pivotal structural question of the life.

### Full Harm Semantics

The MVP reduces harms to realized harmony suppression — they raise energy only when the threatened harmony is currently at full state. The taxonomy describes a broader corrosion: the harming Branch degrades the harmed Branch's alliance capacity even when the third-party harmony partner is absent from the chart. The harmed Branch's ability to form its natural harmony is weakened by the mere presence of its harm partner, regardless of whether the harmony has anything to form with.

Implementing this requires a corrosion edge type that operates on the harmony valence of a Branch rather than on a specific active harmony. The energy term would penalize the harmed Branch's harmony potential proportionally to the harm partner's strength, creating a structural drag on positive alliance formation that persists independently of whether the harmony is active.

### Full Event-Instance Expansion

The MVP collapses repeated stems and branches into family-level switches with deterministic tie-break rules. A chart with the same Branch in two positions gets one family switch, not two independent instance switches. This is a scope-appropriate compression, but it loses information — the two instances may participate in different interactions (one in a harmony, one in a clash), and collapsing them forces a choice that the full system would hold as simultaneous.

The expansion would replace each family switch with position-specific instance switches, increasing the latent state space but allowing the simulation to hold scenarios where the same Branch is harmonized in one position and clashed in another. This is the correct representation for charts with repeated elements, which are common.

---

## III. The Useful God as Emergent Property

The MVP includes a classical heuristic for Day Master strength assessment and a global mode switch for special structures. What it does not include is the simulation-native Useful God determination: injecting each candidate element as a hypothetical pillar and measuring which injection most reduces total system energy.

This is specified in the taxonomy as the operational layer beneath the classical heuristic. The Useful God is not a label assigned by rules — it is the element whose absence creates the most inconsistency and whose presence would most reduce system strain. This can only be computed by running the simulation multiple times with different hypothetical injections and comparing the resulting energy landscapes.

The implementation path: after the natal simulation produces its baseline landscape, run ten additional simulations (five elements × two polarities), each injecting a hypothetical Resource/Output/Wealth/Authority/Companion pillar. Compare total system energies. The candidate producing the greatest energy reduction is the simulation-derived Useful God. When two candidates produce similar reductions, the chart genuinely has two near-equal Useful Gods, and the system reports this as a probability rather than forcing a choice.

This also connects to the temporal dimension: different Luck Pillars bring different elements, and the Useful God may shift across decades as the landscape reconfigures. The natal Useful God identifies the chart's deepest structural need. The temporal Useful God identifies what is most needed right now. These may differ, and the difference is meaningful.

---

## IV. Deeper Rigor in Existing Components

### The Domain Resonance Matrix

The current implementation freezes a 4×5 matrix mapping pillar domains to Ten God groups with specific numeric values. These values are engineering estimates, not rigorously derived. The taxonomy describes domain resonance qualitatively — Output on the Hour pillar is strongly resonant, Resource on the Hour pillar is strongly contradictory — but never provides a systematic derivation.

The honest next step: validate the matrix against a corpus of known charts where domain resonance effects are clearly observable. Adjust values based on empirical signal rather than theoretical intuition. Consider whether the matrix should be asymmetric in ways the current version doesn't capture — whether Resource on Year means something different from Resource on Hour not just in sign but in the shape of the energy term.

### Climate Interaction Calibration

The climate term E_clim penalizes inter-pillar flux under temperature or saturation mismatch. The current implementation uses a quadratic penalty. The taxonomy describes climate interaction more subtly — hot flowing into cold behaves differently from hot flowing into hot, and the difference is qualitative, not just scalar. A production edge carrying energy from a hot-dry pillar into a cold-wet pillar should behave differently from a control edge on the same climate gradient.

The refinement: make the climate interaction term sensitive to edge type, not just aggregate flux. Production under climate mismatch might attenuate (the energy loses force crossing the gradient). Control under climate mismatch might amplify (the restraining force is sharpened by the contrast). This requires extending E_clim from a scalar penalty to an edge-type-conditional function.

### Polarity Beyond a Scalar Multiplier

The current implementation treats polarity as a 1.0/1.2 multiplier — same polarity intensifies by 20%, opposite polarity is neutral. The taxonomy describes a richer distinction: same-polarity production is more aggressive (Eating God), opposite-polarity production is more natural (Hurting Officer). Same-polarity control is more violent (Seven Killings), opposite-polarity control is more civilized (Direct Officer). These are not just magnitude differences — they are qualitatively different relationship types.

The Ten God system already encodes this distinction. But the flux mechanics treat all production edges identically modulo polarity scaling. The refinement would make the flux computation sensitive to the specific Ten God pairing at each edge, not just the elemental relationship and polarity multiplier. A Seven Killings edge would carry a different functional signature than a Direct Officer edge even after accounting for the polarity scaling.

This is where the Composition and Potential planes most need deeper integration. Currently, the energy function has separate terms for elemental flux (Composition) and Ten God role-drift (Potential). The fully integrated version would compute flux itself as a function of both planes simultaneously — the edge weight determined not just by element and polarity but by the functional meaning of the specific Ten God relationship at that edge.

### The Wuxing Interaction Matrix

The frozen matrix assigns specific numeric values to each elemental relationship. Production = +1.0, control = -1.0, drain = -0.5, same-element = +0.5, and asymmetric intermediate values for non-adjacent relationships. These values determine the entire flow topology. They are reasonable starting points but they are not derived from first principles.

The calibration question: are these the right relative magnitudes? Is production really twice as strong as drain? Is same-element reinforcement really half the strength of production? The answers may depend on context — production in a chart dominated by the producing element might behave differently from production in a chart where the producing element is scarce. A context-sensitive interaction matrix — one that modulates its values based on the chart's aggregate elemental balance — would more faithfully represent the taxonomy's description of flows that are simultaneously determined by the total system state.

This is a deep refinement. It makes the interaction matrix itself a function of the state, which adds another layer of recursion to the simultaneous determination. The simulation can handle it — the energy function already handles recursive state-dependence — but the calibration requires extensive validation against known charts.

---

## V. Pattern Language Expansion

### Governor Detection

The motif vocabulary includes chains, loops, cascades, pulses, absences, and bottlenecks. It does not yet include governors — elements or nodes that moderate cascades and loops through control-cycle relationships. A governor is the Metal that prunes the Wood in a Wood-Fire cascade, the Water that douses the Fire in a Fire-Earth loop. When present, the governor prevents runaway amplification. When absent, the system runs without limit.

Governor detection requires identifying, for each active cascade or loop, whether any node in the system holds a control relationship to the cascade's dominant element and has sufficient vitality to meaningfully moderate it. The governor may be present but weak (low vitality, low hierarchy), in which case the moderation exists but barely registers. The governor may be entirely absent, which is the absence motif applied specifically to the cascade's control element.

### Return Path Detection

A return path is a flow that replenishes the source of a drain chain. The ocean drains into the tree — is there anything in the system that feeds the ocean? Return path detection requires tracing from the drain chain's source backward through the production cycle to see if any element producing the source's element exists in the chart with sufficient vitality to constitute meaningful replenishment.

When a return path exists, the drain is sustainable. When it doesn't, the drain runs on initial reserves. The distinction between sustainable and terminal drain is one of the most important diagnostic signals in the system, and it's not yet computed.

### Contradiction Detection

A node where Composition Flow and Potential Flow push in opposite directions. A Resource element (should feed the Day Master) sitting at Death vitality (can't push current). An Authority star (should govern) in the private domain (should be ungoverned). The taxonomy names this as an emergent pattern but the motif extraction doesn't yet detect it.

Contradiction detection requires comparing the Composition-plane flow direction at each node with the Potential-plane functional expectation. When they diverge beyond a threshold, the node is tagged as contradictory. The experience of living with a contradicted node is specific and recognizable — the function exists but can't express cleanly, the role is named but can't be performed.

---

## VI. The Narrative Bridge

### Topology-to-Narrative Grammar

The long source document contains extensive authored content — 120 Stem-on-Branch descriptions, 30 Ten God × pillar position entries, 40 Day Master Lens entries, 48 Branch × pillar position entries. This content is the experiential vocabulary of the system. It describes what individual nodes and bilateral relationships feel like from the inside.

What doesn't exist yet is the grammar for composing this vocabulary into readings that are topology-native rather than node-sequential. The classical reading method goes node by node: this is your Day Master, this is your Month pillar, here is a clash. The topology-native reading goes shape first: here is a cascade from ancestry through career into self, amplifying at each stage, running without a governor because Metal is absent. Then the node-level vocabulary populates the shape — the specific Stem-on-Branch descriptions, the specific Ten God archetypes — giving the structural pattern its experiential texture.

The grammar needs to specify: how motif shapes combine with node descriptions, how basin-level properties (mode, climate, mass) frame the reading, how absences are narrated as structural gaps rather than deficiencies, how multi-basin charts are narrated as superposition rather than ambiguity, how temporal shifts are narrated as landscape deformation rather than events happening to a person.

### The Multi-Model Consensus Layer

The final layer in the original roadmap: a multi-model LLM consensus system that reads the simulation output through the narrative grammar and produces human-readable readings. Multiple models independently generate readings from the same topology. The readings are compared. Where they converge, the signal is strong. Where they diverge, the divergence itself is information — it may indicate genuine ambiguity in the topology or it may indicate that one model has collapsed the landscape in a way the others didn't.

The consensus layer is not a vote. It is a superposition of interpretations — fitting, given that the system it interprets is itself a superposition of states. The final reading presented to the person would carry the convergent insights with confidence and the divergent insights with honest acknowledgment that the topology supports multiple valid readings.

---

## VII. What the System Wants to Become

There is a version of this system where the natal landscape and the temporal flow and the narrative grammar and the consensus layer all operate together. A person enters their birth data. The system computes the natal topology, the current Luck Pillar, the current year, month, day, and hour. Nine pillars. Full cross-connection. Full topology modification. The probability landscape is rendered in real time — shifting every two hours as the hour pillar rotates, shifting every day, every month, every year. The person can scrub through their life timeline and watch the basins form and dissolve, watch cascades activate and governors arrive, watch the Useful God element appear at one frequency and then another and then all frequencies simultaneously in the moments of greatest alignment.

The reading is not a text delivered once. It is a living map that the person returns to, that changes as they change, that shows the structural weather of their current moment against the fixed terrain of their natal topology. The classical BaZi reading was a portrait. This is a weather system — the portrait is the terrain, the temporal flow is the atmosphere, and the reading is the forecast for someone standing on their own specific ground.

Every piece of what this requires has been specified. The taxonomy holds the full structural model. The simulation architecture holds the inference method. The engineering specification holds the buildable math. The visualization holds the interface. The narrative grammar holds the bridge to human meaning.

What remains is execution: building each layer, validating it, placing the next layer on top. The sequence is clear. The architecture supports it. The system is ready to become what it was designed to be — the first complete, non-compressed, n-dimensional reading of a system that has been waiting a thousand years to be held in its full complexity.