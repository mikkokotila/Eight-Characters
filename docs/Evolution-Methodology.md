# Methodology

## What we model

A birth chart is a small directed graph. Four pillars, each containing one visible element (the Stem) and up to three hidden elements beneath it (the hidden stems inside the Branch). Every element has an identity (Wood, Fire, Earth, Metal, Water), a polarity (Yin or Yang), a position in the chart (Year, Month, Day, Hour), and a hierarchy level (Stem, principal, secondary, residual). Every element relates to every other element through the five elemental cycles — production, control, drain, reinforcement, and domination. All relationships are active simultaneously.

The Day Stem is the self — the reference point around which every other element's functional role is defined. These functional roles are the Ten Gods: elements that feed the self (Resource), elements identical to the self (Companion), elements the self produces (Output), elements the self controls (Wealth), elements that control the self (Authority). Each of the ten specific roles carries a different character depending on polarity match.

The chart also contains topology-modifying interactions. Certain pairs of Stems are magnetically attracted and can merge into a new element. Certain pairs of Branches collide, destabilizing everything above them. Others grind chronically. Others merge. Others sabotage each other's alliances. These interactions are predetermined by the specific elements present — they are structural bonding sites that activate or remain dormant depending on what the chart contains.

The question is not what any single element means. The question is what shape the energy makes when all elements, all relationships, and all interactions are held simultaneously.

---

## Why classical methods fall short

A classical BaZi reading processes the chart sequentially. The reader assesses the Day Master's strength, identifies favorable and unfavorable elements, examines each pillar and its Ten God content, notes clashes and harmonies, and weaves a narrative. This produces readings of remarkable depth because the system itself is profound and even a compressed signal carries significant truth.

The compression is threefold.

First, the reader resolves competing interactions by fixed priority rules — "combination neutralizes clash" — when the actual resolution depends on the relative strengths of both interactions, which depend on the vitality of the participating elements, which depends on the seasonal context, which depends on which other interactions are active, which depends on the resolution of the original competition. The recursion is real. The fixed rule collapses it.

Second, the reader assesses Day Master strength as a binary (strong or weak) when it is an emergent property of the total flow entering and leaving the Day Master across all edges simultaneously. A Day Master that appears weak because it lacks same-element support might be effectively strong because a hidden resource in the Hour Branch is feeding it through a chain that passes through two other pillars. The sequential assessment misses the chain.

Third, the reader produces one reading when the chart may genuinely support multiple coherent configurations. A chart where a Stem Combination could transform but might not — depending on whether the seasonal support is sufficient and whether a competing clash is disrupting the bond — doesn't have one correct answer. It has a probability landscape with mass distributed across multiple states. The classical reader must choose. The landscape doesn't.

---

## The energy-based approach

We treat the chart as a physical system with an energy function. Every possible configuration of the chart — which interactions are active, at what strength, which transformations have fired, which elements have changed identity — is a state. Every state has an energy that measures its total internal inconsistency across all constraints simultaneously. Low energy means everything is mutually consistent. High energy means contradictions exist somewhere in the configuration.

The constraints are the structural facts of the system: elemental production should flow in the right direction with the right magnitude, polarity should modulate relationships correctly, vitality should determine throughput capacity, proximity should affect interaction strength, seasonal context should favor certain elements over others, topology modifiers should be consistent with their activation conditions.

The energy function sums contributions from:

**Intra-pillar chemistry.** How well do the elements within each pillar relate to each other? A Stem sitting on a Branch that feeds it has low internal inconsistency. A Stem sitting on a Branch that attacks it has high inconsistency. The flux between every pair of entities within a pillar is computed and summed.

**Inter-pillar flow.** How does energy move between pillars? The directional flux from every entity in every pillar to every entity in every other pillar, weighted by vitality, hierarchy, proximity, and polarity. The sign of the flux (production vs control vs drain) and its magnitude create the chart's primary flow architecture.

**Climate interaction.** Each element carries a temperature (hot to cold) and moisture (wet to dry) signature. Each pillar has an aggregate climate. When strong energy flows between pillars with very different climates, the mismatch raises inconsistency. Hot-dry energy pushing into cold-wet ground behaves differently than the same energy flowing into compatible climate.

**Domain resonance.** Each pillar governs a life domain (ancestry, career, self, inner world). Each element plays a functional Ten God role. Some combinations are resonant — Output content in the inner world pillar amplifies naturally. Some are contradictory — Resource content in the inner world pillar works against the domain's nature. The energy function rewards resonance and penalizes contradiction.

**Topology modifier consistency.** Each active interaction must be consistent with its structural conditions. A Stem Combination claiming full transformation must have seasonal support, must not be opposed by the chart's elemental balance, must not be disrupted by an active clash. An active clash must be consistent with the seasonal strength of both elements involved. Inconsistency between a modifier's claimed state and its actual support raises energy.

**Global chart-structure mode.** In extreme charts, the Day Master may be so weak it surrenders to the dominant element, or so strong that opposing it creates more strain than supporting it. The energy function includes a global mode variable that can shift the entire reading's center from the Day Master to the dominant element. The mode must be consistent with the chart's actual elemental distribution — claiming Follow mode in a balanced chart raises energy.

**Mutual exclusivity.** No entity can be simultaneously transformed by two different interactions into two different elements. This is a hard constraint — violations produce infinite energy, making such states impossible.

The total energy is the sum of all these contributions. The chart's truth is not the single lowest-energy state. It is the full landscape of states weighted by their energy — the probability of each state proportional to how well it satisfies all constraints simultaneously.

---

## Why an energy function

Three properties make this formulation natural for the problem.

**Simultaneity.** The energy function evaluates all constraints at once. There is no order of evaluation, no sequential dependency, no "first assess strength then identify favorable elements." Every constraint contributes to the same scalar energy, and the best states are those where everything is consistent with everything else simultaneously. This matches the system's actual nature — every node determines every other node, with no valid sequential resolution order.

**Competing forces.** The energy function naturally handles tradeoffs. An active harmony lowers energy through one term. An active clash on the same Branch raises energy through another. The net effect depends on their relative magnitudes, which depend on the strength factors, which depend on the chart's state. The system doesn't need priority rules. It has relative energies.

**Multiple solutions.** The energy landscape can have multiple local minima — multiple configurations that are each internally consistent but structurally different from each other. A chart might have a low-energy basin where a harmony has transformed both elements and a different low-energy basin where a clash has disrupted the harmony and the elements remain natal. Both basins are real. The landscape holds both.

---

## Tempered Sequential Monte Carlo

### What it is

Sequential Monte Carlo (SMC) is a method for exploring probability landscapes that are too complex to solve analytically. It maintains a population of particles — each particle is one complete configuration of the system (all interaction states, all strength values, all derived quantities). The population collectively represents the probability landscape. Where many particles cluster, the probability is high. Where few particles exist, the probability is low.

### Why standard sampling fails here

The energy landscape has both discrete variables (which interactions are active, in which state) and continuous variables (how strong each interaction is). It has hard constraints (mutual exclusivity) and soft constraints (everything else). The discrete variables create a rugged landscape with many isolated basins separated by energy barriers. Standard sampling methods — plain Monte Carlo, simple Metropolis-Hastings — get trapped in whatever basin they start in and never discover alternatives.

### How tempering solves this

Tempering introduces an artificial temperature parameter that controls how "picky" the sampling is. At high temperature, the landscape is smoothed — energy barriers shrink, particles can move freely between basins, the population explores broadly. At low temperature, the landscape sharpens — barriers reassert, particles settle into basins, the population concentrates on the genuinely low-energy configurations.

The algorithm starts at high temperature (broad exploration) and gradually lowers it through a sequence of steps (progressive sharpening). At each step, the particles are reweighted to account for the temperature change and then rejuvenated through local moves — discrete proposals that change interaction states and continuous proposals that adjust interaction strengths. By the time the temperature reaches its target, the population has found all significant basins and allocated particles proportionally to each basin's probability mass.

### The specific protocol

We use 1000 particles, 50 temperature steps on a geometric ladder from 10.0 down to 1.0. At each step, five sweeps of rejuvenation alternate between discrete proposals (randomly proposing a new state for one interaction or the global mode) and continuous proposals (randomly adjusting one interaction's strength within its allowed range). Proposals are accepted or rejected by the Metropolis-Hastings criterion — the probability of acceptance depends on whether the proposed change reduces or increases energy at the current temperature.

When the effective sample size (a measure of how evenly the probability mass is distributed across particles) drops below half the population, systematic resampling redistributes the particles — duplicating high-weight particles and dropping low-weight ones — to prevent the population from degenerating into a few particles carrying all the mass.

The protocol is fully deterministic given a fixed random seed, meaning identical inputs always produce identical outputs.

---

## Interaction strengths as ranges

Each topology-modifying interaction has a continuous strength parameter bounded by a range rather than set to a fixed value. The range bounds are determined by structural properties already in the model:

**Vitality** of participating elements sets the ceiling. Elements at Peak can support strong interactions. Elements at Death cannot sustain much of anything.

**Proximity** of the pillars involved. Adjacent pillars form stronger interactions than distant ones. A combination between Day and Hour Stems (adjacent) has a higher strength ceiling than the same combination between Year and Hour (maximum distance).

**Seasonal support.** The Month Branch determines which element is in power. Interactions whose target element is seasonally empowered have higher ceilings. Those opposing the seasonal element have lower ceilings.

Within these bounds, the simulation explores. The final strength value for each interaction in each particle is wherever the sampling settled — not a predetermined answer but an emergent property of the full constraint satisfaction.

---

## Post-processing

### Relaxation

After sampling, each particle is polished to its nearest local energy minimum. Discrete relaxation iterates through all interaction switches, greedily accepting any state change that reduces energy, until no improvement remains. Continuous relaxation uses gradient descent on the strength parameters, nudging each toward the value that minimizes energy given the current discrete state. The result is a population of clean, locally optimal configurations rather than noisy samples.

### Clustering

The relaxed particles are clustered using DBSCAN — a density-based algorithm that groups particles by similarity without requiring the number of clusters to be specified in advance. Two particles are similar if they share the same interaction states, the same effective element identities, and similar strength values. Dense regions of similar particles become basins. Isolated particles become noise.

### Why DBSCAN

It finds the number of basins naturally rather than requiring it as an input. A chart with one coherent configuration produces one basin. A chart in genuine superposition produces two or three. The algorithm discovers this from the data rather than being told.

### Basin characterization

Each basin is summarized by its probability mass (what fraction of particles landed there), its MAP exemplar (the lowest-energy particle in the basin, representing the basin's most coherent configuration), and a set of derived properties computed from the MAP exemplar: global mode, chart climate, effective elements, effective Ten Gods, and the motif inventory.

---

## Motif extraction

The MAP exemplar of each basin defines a directed graph of entity-to-entity flux values. Motif extraction identifies structural patterns in this graph — shapes that emerge from the flow topology and that no sequential reading would discover.

An active-edge threshold filters out weak connections, keeping only edges carrying at least 25% of the strongest edge's magnitude. This reveals the primary flow architecture.

**Chains** are maximal directed paths where energy flows consistently in one direction through two or more nodes. They reveal where energy originates, where it terminates, and what happens at each node along the way.

**Loops** are directed cycles where energy circulates without exit. They reveal self-sustaining or self-consuming patterns — energy trapped in repetition.

**Cascades** are chains where the signal amplifies at each node — the flux magnitude grows along the path. They reveal where the topology produces exponential intensification.

**Pulses** are nodes with high balanced throughput in both directions — simultaneously receiving and emitting at above-median levels. They reveal points of rhythmic oscillation rather than steady flow.

**Bottlenecks** are nodes carrying disproportionate throughput relative to their vitality. They reveal where the system's strain concentrates — the pressure points.

**Absences** are elements with zero presence anywhere in the chart. They reveal structural gaps that shape every flow by their non-existence — the functions no node can perform because the element that performs them isn't there.

These patterns are not interpretations. They are structural features of the flux graph, detected by deterministic algorithms, reported without narrative framing. What they mean in the context of a life is a separate question — one that the visualization and the reading practice address, but that the methodology itself deliberately leaves open.

---

## What the output is

The engine produces a probability landscape: a set of basins, each with a probability mass, a characteristic configuration, a climate, a mode, and a motif inventory. The landscape may contain one basin (certainty) or several (superposition). It includes a noise mass for particles that didn't cluster into any basin.

The output is not a reading. It is not a narrative. It is not a verdict about the chart. It is the set of internally consistent configurations the chart supports, weighted by how well each satisfies all structural constraints simultaneously, with the emergent flow patterns identified and labeled.

Everything downstream — visualization, interpretation, narrative — builds on this output but is not part of this methodology. The methodology's commitment is to hold the full complexity without compressing it, to let the topology speak through its own structural logic, and to report what it finds with precision and without editorial.

---

## Validation

The system validates at three levels.

**Internal consistency.** Repeated runs with the same input and seed produce identical outputs. Energy conservation holds — the total energy of each particle is the exact sum of its component terms. Weight normalization holds — particle weights sum to one after every reweighting step. These are checked by automated tests.

**Structural plausibility.** Known chart configurations produce expected topological features. The deepest self-reinforcing pillar in the system (Ren on Zi) should show maximum retention. The most depleted conduit (Jia on Wu at Death) should show minimum vitality. Charts with obvious clashes should activate those clashes. Charts with obvious harmonies should activate those harmonies. These are checked against the taxonomy's qualitative expectations.

**Interpretive resonance.** The topology, when read by someone who knows the person whose chart it is, should produce recognition. Not prediction — recognition. The person should see the shape of their own life in the landscape. This is the hardest validation and the most important one. It cannot be automated. It requires human contact with the output and honest reporting of whether the topology matches the felt experience of being alive in this particular configuration.

The system does not claim to be correct. It claims to be more complete than any previous method — holding dimensions that sequential reading necessarily compresses. The validation is whether that additional completeness produces readings that match reality more faithfully than the compression did. Early evidence suggests it does. The evidence will accumulate as more charts are run and more people encounter their own topology for the first time.