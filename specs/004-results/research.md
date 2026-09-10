# Research: Results

**Phase 0 output** for [plan.md](./plan.md). Six decisions.

Nothing new was needed. This phase reads what Phases 1 and 2 already store.

---

## R1, One function decides state, and Phase 4 will import it

**Decision**: `state.py` holds `state_for(test, attempts) -> State`, where `State` is an enum of the five values. It takes already-fetched rows, touches no database, and knows nothing about who is asking.

```
no test available   test is None or unpublished
in progress         an unsubmitted attempt exists
not started         no submitted attempt at this test
passed / failed     most recent submitted attempt, against the pass mark
```

**Rationale**: FR-017 requires the instructor's view to use the same states decided the same way, and Phase 4 adds *due* and *overdue* on top of the same five. Three call sites need one rule. A pure function means the rule exists once, is trivially testable across every combination, and can be imported by Phase 4 without dragging a database session along.

**Alternatives considered**: computing state inside each query (rejected, three copies of the rule, and they will diverge); a `state` column on registration (rejected, FR-025 forbids storing it, and a stored state goes stale the moment an attempt is submitted).

---

## R2, Attempts at a replaced test do not count

**Decision**: The state query filters attempts to the module's **currently published** test. A person's attempts at any earlier test are excluded from state, and appear only in their history.

**Rationale**: FR-008. Phase 2 freezes a test once attempted, so an instructor needing changes publishes a replacement, and the module now asks something different, so passing the old one does not mean passing this one.

The practical consequence is large and worth stating once: **publishing a replacement resets everyone on that module**. FR-027 requires warning the instructor beforehand with the number of people affected, which is why R6 exists.

**Alternatives considered**: counting attempts at any test on the module (rejected, a person would show "passed" for a test they never saw); carrying the old pass forward with a marker (rejected, a sixth state and an explanation, for a case the owner already decided).

---

## R3, One query, not one per module

**Decision**: `results_service.for_person(user)` runs a single query joining registration, test, and attempt, ordered so that Python groups rows by module in one pass. Same shape for the instructor's view, grouped by person instead.

**Rationale**: The obvious implementation, loop the registrations, query each module's test, query each person's attempts, is thirty modules times three queries. SC-008 asks for a usable page at thirty modules, and SQLModel's lazy loading makes the slow version the one you get by accident.

**Alternatives considered**: eager loading via relationships (rejected, still several queries, and harder to see what is happening); caching (rejected, nothing here is expensive enough to justify a cache, and a cache of derived state is a stored state by another name).

---

## R4, Ordering by what is outstanding

**Decision**: Sort in Python after grouping, on a rank derived from state:

```
trainee's own page (FR-007)        instructor's cohort (FR-020)
  1 failed                           1 failed
  2 not started                      2 not started
  3 in progress                      3 in progress
  4 passed                           4 passed
  5 no test available                5, then by name within each rank
```

**Rationale**: Both requirements say outstanding things come first, and the state is already computed by the time sorting happens. Sorting in SQL would mean expressing the state rule in SQL as well as in Python, the same rule in two languages, which is the duplication R1 exists to avoid.

**Alternatives considered**: sorting in the query (rejected, duplicates the state rule in SQL); letting the person sort (rejected, a feature nobody asked for).

---

## R5, States legible without colour

**Decision**: Every state renders as a Bootstrap badge carrying **both** a colour and its own word, "Passed", "Failed", "Not started", "In progress", "No test". The word is never dropped in favour of the colour alone, and never abbreviated to an icon.

**Rationale**: FR-023. It is also the cheaper option: a badge with text needs no legend, no tooltip, and no explanation, and it survives being printed or screenshotted in greyscale.

**Alternatives considered**: coloured dots with a legend (rejected, a legend is a second thing to read); icons only (rejected, icons mean different things to different people).

---

## R6, Counting who a replacement will reset

**Decision**: `results_service.count_affected_by_replacement(module)` returns how many registered people currently show "passed". The Phase 2 publish route calls it before showing the confirmation, and the confirmation names the number.

**Rationale**: FR-027 requires the warning to say how many people it is. A vague "this will reset trainees" is ignored; "this will reset 30 people to not started" is not. The count reuses the same state function, so the number shown is exactly the number that will change.

**Alternatives considered**: warning without a number (rejected, FR-027 asks for the count); counting registrations rather than passes (rejected, it would overstate, since people who never passed lose nothing).

---

## Notes for implementation

- **The instructor's own modules do not appear in their personal results** (FR-015). The query filters `role_in_module = 'trainee'`. Someone registered on a module in both capacities sees it in both places, which is correct.
- **A removed registration disappears on the next page load** (FR-014). Nothing needs to happen, the row is gone, so the join returns nothing.
- **An expired attempt is submitted on read** (Phase 2, research R8). The results page is one of the places that triggers it, so a person returning to a lapsed attempt sees "failed" rather than "in progress".
- **Nothing on these pages writes.** No score entry, no adjustment, no weighting (FR-026). Correcting a score stays where Phase 2 put it, on the attempt.
