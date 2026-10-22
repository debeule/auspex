# Feature Name

**Status:** draft
**Blocked by:** —
**Branch:** `feature/descriptive-name`
**Docs impact:** `NS-new` (owner doc) · changed: … · retired: … — or `none — <reason>`

---

## Context

What already exists that this feature builds on or integrates with. File paths, interfaces, relevant requirement IDs. Enough that a cold session can orient itself without reading the whole codebase.

## What this builds

What the system can do when this spec is done that it cannot do now. Concrete, not abstract.

## Out of scope

Hard boundary — what this spec explicitly does not include. At least one line.

## Constraints

Which invariants (`INV-n`) and owner-doc requirements apply, by ID, never restated. Any specific traps or non-obvious constraints unique to this feature.

## Required tests

Write these first. Confirm each fails for the right reason before implementing (ENG-001). Map each to the requirement ID it verifies.

- `test_name` — what behaviour or invariant this guards
- `test_name` — edge case description

## Definition of done

```bash
# replace with the actual verify command
uv run pytest tests/unit/test_feature.py -q
```

Expected: N passed

## Compatibility

What keeps working while this change rolls out, and what a reader of the old behaviour must know.

## Rollback

How to undo the change if it has to come out.

## Notes

Non-obvious decisions, known traps, open questions that need a decision before starting.

## Handoff

Only when a session stops before the spec is done:
- Written against: develop @ <sha>; branch `…`, N commits ahead
- Done:
- Not done:
- Next:
- Docs:
- Open decisions:
- Verify:
