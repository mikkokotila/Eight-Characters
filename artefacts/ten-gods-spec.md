# Product Requirements Document (PRD): Ten Gods Derivation & Percentile Distribution

## 1. Feature Overview

The objective of this feature is to deterministically resolve the **Ten Gods (Shi Shen)** for a given Four Pillars chart and compute a **Percentile Distribution** showing the relative composition of the chart based on those Ten Gods.

Since input validation, payload structures, and internal architectural patterns are already established, the engineering team has full autonomy over the "how" (API design, data models, memory management). This document defines the exact, opinion-free mathematical and relational logic (the "what") required to guarantee accurate, reproducible results.

## 2. Dependencies

Engineers must integrate the following existing assets to prevent hardcoding static rules or duplicating logic:

* **Existing Hidden Stems API/Module:** The system must utilize our existing internal service to retrieve the Hidden Stems for the 4 Earthly Branches.
* **Lookup Artefact (`artefacts/ten-gods.csv`):** This static file serves as the absolute source of truth for mapping the relationship between a Day Master and a target stem to a specific Ten God.

---

## 3. Deterministic Business Logic (The "What")

The calculation pipeline must execute the following logical sequence.

### Step 1: Establish the Anchor (Day Master)

1. Extract the Heavenly Stem of the **Day Pillar** from the user's validated input.
2. This specific stem is designated as the **Day Master (DM)**. It acts as the relational anchor for all subsequent Ten God lookups.
3. *Product Rule:* The Day Master itself is **excluded** from the evaluation pool, as it represents the "Self" and does not evaluate a Ten God relationship against itself.

### Step 2: Assemble the Evaluation Pool

Gather all other elements in the chart to form a single evaluation pool to be mapped.

1. **Visible Stems:** Collect the Heavenly Stems from the **Year**, **Month**, and **Hour** pillars (exactly 3 items).
2. **Hidden Stems:** Pass the 4 Earthly Branches (Year, Month, Day, Hour) to our existing **Hidden Stems API**. Collect every hidden stem returned by the service.
3. **Total Pool Size ():** .

### Step 3: Map the Ten Gods

For every single stem in the evaluation pool (both visible and hidden):

1. Query `artefacts/ten-gods.csv`.
2. Perform an exact match lookup using:
* **Key 1:** The Day Master (from Step 1)
* **Key 2:** The current target stem from the evaluation pool


3. Attach the resulting Ten God string (e.g., "Eating God", "Direct Wealth") from the CSV to that specific stem's data object in the chart structure.

### Step 4: Calculate the Percentile Distribution

To provide a macro-view of the chart's elemental composition, calculate the percentile share of each Ten God.

*(Product Note: To guarantee determinism in this baseline iteration, all stems are treated equally. 1 stem = 1 unit of mathematical weight. Do not introduce subjective domain weighting for Main vs. Residual Qi).*

1. **Determine Total Population ():** Use the total size of the evaluation pool calculated in Step 2.
2. **Count Occurrences ():** Group the evaluation pool by the assigned Ten Gods. Count exactly how many times each specific Ten God appears in the chart.
3. **Calculate Share:** For each Ten God present, apply the formula: `(C / N) * 100`.
4. **Rounding Rule:** To prevent floating-point UI inconsistencies across clients, round all final percentages to exactly **two decimal places** (e.g., `14.29%`) using standard half-up rounding.

---

## 4. Expected Product Deliverables

Regardless of the specific JSON shape or internal data structures the engineering team decides to implement, the final output payload must successfully expose:

1. The identified **Day Master**.
2. The fully mapped chart, explicitly pairing every visible stem (Year, Month, Hour) and every resolved hidden stem with its calculated **Ten God**.
3. A **Distribution Summary** detailing the exact percentile share of every Ten God present in the chart. The sum of all active percentile shares must equal ~100% (accounting for standard rounding limits).