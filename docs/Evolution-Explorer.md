# Evolution Explorer — Canonical Reference

## What this is

Evolution Explorer is a visual interface for reading the probability landscape produced by the BaZi Wuxing natal evolution engine. It renders the energy topology of a birth chart as a directed flux graph with motif overlays, supported by a classical pillar strip and a basin metadata panel.

The visualization does not interpret. It shows what the simulation found — which configurations are probable, where energy flows, where it's blocked, what's missing, and how the topology modifies itself through clashes, harmonies, punishments, and transformations.

---

## Header Bar

| Label | What it shows | How to read it |
|---|---|---|
| Basin 1/N (id X) | Which basin is currently displayed, out of how many total | One basin means one coherent identity. Multiple basins mean the chart exists in superposition between structurally different configurations. Navigate between basins to see how the topology changes. |
| Mass | Probability mass of the displayed basin | How much of the simulation's particle cloud settled into this configuration. 100% means no ambiguity. 60/40 split means genuine structural tension between two ways of being. |
| Mode | Global chart-structure mode at MAP | Standard means the Day Master holds its own identity. Follow types mean the Day Master has surrendered to a dominant element and the entire reading reorients around that element. |
| Chart T | Aggregate chart temperature Θ_chart | Position on the hot ← → cold spectrum. Positive is warm/hot. Negative is cool/cold. Computed from all entities' elemental climate signatures weighted by hierarchy. |
| Chart S | Aggregate chart saturation Sat_chart | Position on the wet ← → dry spectrum. Positive is moist/wet. Negative is dry. Same computation method as temperature. |

---

## Layer 1 — Flux Graph

The primary visualization. A directed graph where nodes are entities (stems and hidden stems) and edges are energy flux values F(i→j).

### Node Properties

| Visual Property | What it encodes | How to read it |
|---|---|---|
| Position — column | Pillar (Year / Month / Day / Hour) | Left to right: ancestry, career, self, inner world. |
| Position — row | Hierarchy level (Stem / Principal / Secondary / Residual) | Top to bottom: visible stem, then hidden stems in descending strength. Stems are the visible characters of the chart. Hidden stems are the terrain beneath. |
| Size | Dynamic vitality amplitude ã_i | How much functional capacity this entity has after clash and punishment damage. Large nodes push and receive strong current. Small nodes are depleted or structurally inert. A tiny node in a prominent position (like an Eating God at Death on the Month pillar) means the function is structurally present but energetically hollow — a conduit, not a container. |
| Fill color | Effective element ẽ_i | Wood, Fire, Earth, Metal, Water — shown in the legend. After full transformation, color reflects the transformed element, not the natal one. |
| Border color/style | Ten God group (Self / Output / Wealth / Authority / Resource) | The functional role this entity plays relative to the Day Master (or the active mode center in Follow configurations). Self = same element. Output = what the center produces. Wealth = what the center controls. Authority = what controls the center. Resource = what feeds the center. |
| Label | Entity identifier, element name, Ten God name | Tap for full detail card. |

### Edge Properties

| Visual Property | What it encodes | How to read it |
|---|---|---|
| Thickness | Absolute flux magnitude |F(i→j)| | Thicker edges carry more energy between the two entities. The thickest edges are the chart's primary energy highways. |
| Color | Flux relation type | Production (energy flowing forward in the elemental cycle — feeding), Control (energy cutting across the cycle — restraining), Drain (energy flowing backward — depleting the source). |
| Direction | Arrow from source to destination | Energy flows from source toward destination. The source is being spent. The destination is being fed, pressured, or drained depending on the relation type. |
| Opacity / visibility | Controlled by the minimum |F| slider | Filter out weak edges to reveal the dominant flow structure. Raising the threshold strips away noise and shows only the heaviest channels. |

### Motif Overlays

Toggleable highlights that reveal emergent topological patterns in the MAP exemplar's flux graph. These are the shapes the energy naturally forms — not predefined meanings but structural features discovered by the simulation.

| Motif | What it is | How to read it |
|---|---|---|
| Chains | Directed paths of length ≥ 2 with consistent edge signs | Where energy flows in one direction through multiple nodes. A chain from Year to Month to Day is ancestral momentum carrying through career into self. The chain's direction tells you where energy originates and where it terminates. A chain through a low-vitality node means that node is a conduit — everything passes through, nothing stays. |
| Loops | Directed simple cycles of length ≥ 2 | Where energy circulates without exit. A self-sustaining pattern if it accumulates per cycle, a self-consuming pattern if it depletes. Loops between two nodes in the same pillar show internal circulation within that life domain. Loops across pillars show energy cycling between life domains without resolution. |
| Cascades | Chains with nondecreasing edge magnitudes and amplification ratio ≥ 1.25 | Where the signal gets louder as it flows. Each node in the cascade amplifies rather than attenuates. This is the topology's exponential — output on output pillar with function matching domain matching elemental direction. Cascades identify where the chart's most intensified patterns live. |
| Bottlenecks | Nodes in the top quartile of throughput-to-vitality ratio | Where the system is constrained. High energy flowing through low capacity. The pressure point. Bottleneck nodes are doing more work than their vitality can cleanly sustain. They are where the chart's strain concentrates. |
| Pulses | Nodes with balanced above-median inbound and outbound flux | Where energy oscillates rather than flowing through. The node is simultaneously being heavily fed and heavily drained, creating a rhythm of accumulation and release rather than a steady current. |
| Absent Ghosts | Placeholder nodes for elements with zero presence in the MAP state | What's missing. The ghost shows where the absent element would sit and what edges would exist if it were present. Absence isn't emptiness — it's a structural gap that shapes every flow by its non-existence. The absent element's roles (Resource, Governor, etc.) are shown in the callout. |

### Controls

| Control | What it does |
|---|---|
| Min |F(i→j)| slider | Sets the minimum absolute flux threshold for visible edges. Raising it strips weak connections and reveals dominant flow architecture. |
| Fit | Recenters and rescales the graph to fit the viewport. |
| Reset Filters | Returns all toggles and slider to default state. |
| Edge Relations checkboxes | Toggle visibility of Production, Control, and Drain edges independently. Useful for isolating one type of relationship — e.g., showing only production edges reveals the feeding chains, showing only control edges reveals the pressure architecture. |
| Motif Overlays checkboxes | Toggle each motif highlight independently. Layer them to see how patterns overlap — a chain that is also a cascade, a bottleneck that sits inside a loop. |

### Node/Edge Tap Detail

Tapping any node, edge, motif segment, or absent ghost opens a detail panel.

| Tap target | Detail shown |
|---|---|
| Node | Entity index, element, polarity, hierarchy level, pillar position, Ten God identity, Life Stage, dynamic vitality amplitude, temperature and moisture contribution. |
| Edge | Source and destination entities, flux value F(i→j), absolute magnitude, relation type (production/control/drain), component breakdown (elemental relationship, polarity modifier, vitality differential, proximity weight). |
| Motif segment | Motif type, participating nodes listed in order, edge magnitudes along the path, amplification ratio for cascades. |
| Absent ghost | Missing element, what roles it would fill relative to the Day Master (Resource, Governor, etc.), which active motifs it would modify if present. |

---

## Layer 2 — Pillar Strip

A horizontal classical reference showing the four pillars in traditional BaZi format, connected to the topology above.

### Per-Pillar Fields

| Field | What it shows | How to read it |
|---|---|---|
| Domain label | Year = Ancestry, Month = Career, Day = Self, Hour = Inner World | The life area this pillar governs. |
| Stem | Chinese character, pinyin, archetype name | The visible element sitting on this pillar — the character the world sees. |
| Branch | Chinese character, pinyin, animal name | The terrain beneath the stem — the environment, the hidden ground. |
| Life Stage | Stage number and classical name | The vitality condition of the stem on its own branch. Peak means sovereign power. Death means the form is present but function has ceased. Birth means fresh vital energy. This is a permanent structural property of the pillar, not a temporal condition. |
| Ten God | Ten God identity relative to active mode center | The functional role this pillar's stem plays in the chart's energy system. |

### Cross-Pillar Bands

| Visual | What it shows | How to read it |
|---|---|---|
| Colored bands spanning two or more pillars | Active topology modifiers (clashes, punishments, harmonies, etc.) | Red bands for clashes — the two pillar grounds are in structural collision. Amber bands for punishments — chronic friction between the grounds. Blue bands for harmonies — the grounds are merging. The band connects the pillar positions involved. |

---

## Basin Metadata Panel

A compact summary panel showing basin-level signals and comparison tools.

### Sections

| Section | Content | How to read it |
|---|---|---|
| Global Mode | Active chart-structure mode at MAP | Standard means the Day Master is the center of the reading. Follow types mean the center has shifted. This single label reframes every Ten God assignment in the chart. |
| Climate Quadrant | Visual position on temperature × saturation grid | The chart's aggregate felt-sense. Cold-wet is the ocean's signature. Hot-dry is the furnace's signature. The quadrant gives an immediate bodily intuition before any structural analysis. |
| Basin Mass | Probability bar showing all basins | How the simulation's mass is distributed. One full bar means certainty. Split bars mean the chart lives between configurations. The bar makes superposition visible at a glance. |
| Switchboard Delta | Comparison between current basin and a reference basin | When multiple basins exist, shows which topology switches differ — which clashes, harmonies, or transformations are active in one basin but not the other. This is how you see what structurally distinguishes two possible versions of the same chart. |
| Active Topology Switches | List of all non-zero S_r with state and omega values | Which topology modifiers the simulation activated in this basin's MAP exemplar, and at what strength. Higher omega means the interaction is more dominant. This is the chart's active modification layer — which mergers, collisions, frictions, and sabotages are structurally present. |
| Firing Transformations | List of full-state transformations (S_r = full) | Which stems or branches have abandoned their natal element and become something new. No firing transformations means the chart operates with its natal elements intact. Active transformations mean identity has structurally shifted. |
| Motif Inventory | Count of each motif type, with delta vs reference basin | Summary count of chains, loops, cascades, bottlenecks, pulses. The delta shows how the motif landscape changes between basins. More loops in one basin versus another means one configuration circulates more energy internally. |
| Absence Callout | Missing elements with their functional roles listed | Which elements have zero presence anywhere in the MAP state, and what those elements would do if they existed — Resource (feeds the center), Governor (moderates cascades), etc. The absence callout is often the single most important diagnostic signal in the chart. |

### Footer

| Label | What it shows |
|---|---|
| Nodes visible | Count of active entity nodes in the current view. |
| Directed edges visible | Count of flux edges passing the current filter threshold. |
| Motif segments | Count of highlighted motif path segments in the current view. |
| Topology modifiers | Count of active non-zero topology switches. |

---

## Reading Order

For someone encountering a chart for the first time, the recommended reading order is:

1. **Header** — how many basins, what mode, what climate. This tells you whether the chart is singular or in superposition, whether the self holds center or has surrendered, and what the chart feels like before you look at structure.

2. **Absent ghosts** — what's missing. The structural gap shapes everything else. Know what isn't there before you read what is.

3. **Node sizes** — where is vitality concentrated, where is it depleted. The largest node is the chart's center of gravity. The smallest node in a prominent position is a conduit, not a container.

4. **Thickest edges** — where does the most energy flow. Raise the minimum flux slider until only the heaviest channels remain. This is the chart's primary architecture.

5. **Motif overlays** — turn on chains first to see directional flow, then cascades to see where it amplifies, then loops to see where it circulates, then bottlenecks to see where it's pressured.

6. **Active topology switches** — which clashes, punishments, harmonies are firing and at what strength. These modify the baseline flow. The highest-omega switch is the loudest active force in the chart.

7. **Pillar strip** — ground the topology in life domains. Which pillar holds the largest node, which holds the smallest, which are connected by clashes or harmonies.

8. **Basin comparison** (if multiple basins) — switch between basins and watch what changes. The switches that flip between basins are the structural hinges of the chart's ambiguity.