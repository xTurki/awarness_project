# Data Model: Results

**Phase 1 output** for [plan.md](./plan.md).

**This phase adds no tables, no columns, and no volume.** FR-025 requires everything to be derived from what already exists, so what follows is not a schema but the rules that turn existing rows into what the two pages show.

---

## What it reads

| From | Phase | Used for |
|---|---|---|
| `registration` | 1 | Which modules appear for a person, and in what capacity |
| `module` | 1 | Title, and whether it is published |
| `test` | 2 | Whether the module has anything to complete, and the pass mark |
| `attempt` | 2 | Score, outcome, history, and whether one is in progress |

Nothing is written. There is no results table, no cached state, no summary row.

---

## The state rule

One function, `state_for(test, attempts)`, applied per person per module. Evaluated in this order, the first match wins:

| # | Condition | State |
|---|---|---|
| 1 | No test on the module, or it is unpublished | **no test available** |
| 2 | An attempt exists that is not submitted | **in progress** |
| 3 | No submitted attempt **at the currently published test** | **not started** |
| 4 | Most recent submitted attempt scored at or above the pass mark | **passed** |
| 5 | Otherwise | **failed** |

### Two things the order settles

**Rule 3 filters by the currently published test** (FR-008). Attempts at a test that has since been replaced are excluded here, though they still appear in the person's history. This is what makes publishing a replacement reset the whole cohort.

**Rule 4 uses the most recent submitted attempt**, not the best (FR-005). Someone who scored 40, then 90, then 70 with a pass mark of 80 is **failed**, the same rule Phase 2 applies and Phase 4 will apply to due dates.

### The score shown

Whatever the deciding attempt scored, including an instructor's override, Phase 2 stores an override in the same column, so nothing here needs to know one happened.

A state with no deciding attempt shows no score (FR-004).

---

## What each page derives

### A person's own results (FR-001)

One row per registration where `role_in_module = 'trainee'`, a module someone only instructs is not training they owe (FR-015).

```
module title · state · score (where one exists) · a way in
```

Ordered by outstanding first (research R4), and a person with no registrations sees a statement saying so rather than an empty table (FR-024).

### One module's history for one person (FR-009)

Every attempt that person has made at that module's tests, **including at replaced tests**, which is the one place they remain visible.

```
date · score · outcome · a link to the review from Phase 2
```

An attempt in progress leads back into the attempt itself rather than a review (FR-011).

### An instructor's cohort (FR-016)

One row per person registered as a trainee on that module.

```
name · state · score · a way into their attempts
```

Same five states, decided by the same function (FR-017). Ordered so those who have not passed come first (FR-020).

---

## Deliberately not derived

| Not shown | Why |
|---|---|
| Anything spanning more than one module | FR-021, no organisation-wide view exists |
| An average, a trend, or a comparison between people | Out of scope |
| A completion certificate or printable record | Out of scope |
| A count of how many people passed, on a person's own page | The instructor's view covers one module; nothing aggregates |

---

## One value computed for Phase 2

`count_affected_by_replacement(module)` returns how many registered people currently show **passed**. Phase 2's publish route calls it to fill in the warning that FR-027 requires, "this will reset 30 people to not started". It uses the same state function, so the number shown is exactly the number that changes.
