# Feature Name

**Status:** draft
**Blocked by:** —
**Branch:** `feature/descriptive-name`

---

## Context

What already exists that this feature builds on or integrates with. File paths, interfaces, relevant invariants. Enough that a cold session can orient itself without reading the whole codebase.

## What this builds

What the system can do when this spec is done that it cannot do now. Concrete, not abstract.

## Out of scope

Hard boundary — what this spec explicitly does not include. At least one line.

## Constraints

Which architecture invariants from root `CLAUDE.md` apply. Any specific traps or non-obvious constraints unique to this feature.

## Required tests

Write these first. Confirm each fails for the right reason before implementing.

- `test_name` — what behaviour or invariant this guards
- `test_name` — edge case description

## Definition of done

```bash
# replace with the actual verify command
uv run pytest tests/unit/test_feature.py -q
```

Expected: N passed

## Notes

Non-obvious decisions, known traps, open questions that need a decision before starting.
