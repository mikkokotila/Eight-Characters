**Taxonomy.md** is the source of truth for what the system models. Every design decision in the-math.md traces back to a structural fact in the taxonomy. When in doubt about meaning, the taxonomy wins.

**Math.md** is the source of truth for how it is built. Every variable, equation, constant, algorithm, and protocol is specified. When in doubt about implementation, the math wins.

**Contracts:**

1. **No design decisions.** The engineer implements what is specified. If something appears ambiguous, it is a question for the author, not a judgment call for the engineer.

2. **No additions.** If a feature is not in the-math.md, it does not get built, even if the-taxonomy.md describes it. The scope boundaries in Section 9 of the-math.md are explicit. Deferred means deferred.

3. **No simplifications.** If the-math.md specifies a computation, it is performed exactly as written. No approximations, no shortcuts, no "this is equivalent." The frozen constants are frozen. The numerical protocol is frozen. The PRNG seed is frozen.

4. **Consult the taxonomy for validation.** After building, test outputs should make sense against the taxonomy's qualitative descriptions. Ren on Zi should present as the deepest, most self-reinforcing pillar. Jia on Wu should present as maximum outward drain. If the output contradicts the taxonomy's qualitative expectations, something is wrong in the implementation, not in the specification.

5. **Report, don't interpret.** The build produces basin masses, MAP exemplars, motif inventories, climate coordinates, and active modes. It does not produce narrative readings. Interpretation is a separate layer that comes later.

6. **Extensibility is sacred.** The taxonomy describes a nine-pillar temporal system, full harm corrosion, storage-gate switches, directional combinations, and Useful God gradient injection — none of which are in the current build. Every implementation choice must leave room for these additions. No architectural decision should make future expansion require a rewrite.