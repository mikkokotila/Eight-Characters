```markdown
---
alwaysApply: true
---

**The crucial key point is that this project lives in the world of pure mathematics meeting human life, neither of which can afford error. Therefore, the key principle to always follow is to avoid regression at all cost, and to avoid introducing new issues at all cost.

## Non-negotiables

- No workarounds. Find the root cause, fix it.
- No fallbacks. Let things break and make noise.
- No silent failures. If something goes wrong, surface it.
- No swallowed exceptions. If it's caught, it's handled or re-raised.
- Nothing deployment-specific is ever hard-coded. If a value changes between local, CI, and production, it is an environment variable. No exceptions.
- Commit with clear conventional commits message after every sub-slice, and after any inter-slice work

```