# Quickstart: Results

**Phase 1 output** for [plan.md](./plan.md). How to prove this phase works.

Each scenario maps to a user story in [spec.md](./spec.md).

---

## Prerequisites

Phases 0, 1, and 2 working. You need one module with a published test, an instructor, and **four trainees in four different states**:

| Trainee | Set up by |
|---|---|
| Never attempted | Register them and stop |
| In progress | Start an attempt, close the browser |
| Passed | Take it and score above the pass mark |
| Failed | Take it and score below |

Plus a fifth module with **no test at all**, with one trainee registered on it.

```bash
docker compose up -d --build   # no new tables in this phase
```

Nothing new in `.env`. Nothing new to migrate, this phase stores nothing.

---

## Scenario 1, A trainee sees where they stand *(US1, P1)*

Sign in as the trainee registered on all five modules.

| Module | Expect |
|---|---|
| Never attempted | **Not started** |
| In progress | **In progress** |
| Passed | **Passed**, with the score |
| Failed | **Failed**, with the score |
| No test | **No test**, not "not started" (FR-006) |

Then:

3. Confirm **outstanding modules appear first**, failed and not started above passed (FR-007).
4. Confirm modules they are *not* registered on do not appear at all.
5. Have the trainee score 40, then 90, then 70 with a pass mark of 80. Their state must read **failed** and their score **70**, the most recent, not the best (FR-005).
6. Request `/results/modules/{id}` for a module they are not on. Expect **404**.

---

## Scenario 2, Look into one module *(US2, P2)*

1. Open a module with three attempts from the results page.
2. All three appear with date, score, and outcome.
3. Open any one, you reach the Phase 2 review showing your answers and the correct ones.
4. Open a module with no attempts, you are told there is nothing yet, and offered the test.

---

## Scenario 3, Pick up something unfinished *(US3, P3)*

1. The trainee with an open attempt sees that module as **In progress**.
2. Following it lands **back in the attempt**, not on a review, with the answers already given intact.
3. Now let an attempt run past its deadline without submitting. Reload the results page, it now reads **passed** or **failed** on what was answered, not "in progress" (Phase 2 submits it on read).

---

## Scenario 4, The instructor's cohort *(US4, P2)*

Sign in as the **instructor**.

1. Open the module's results. All four trainees listed with their states and scores.
2. Those who have not passed appear **first** (FR-020).
3. Open one person, you reach their attempts, and from there any individual attempt.
4. Request the results of a module you do not run. Expect **403**.
5. Look for any view covering more than one module. **There is none** (FR-021).
6. Confirm the instructor's **own** results page does not list the module they teach (FR-015).

---

## Scenario 5, Replacing a test resets the module *(FR-008, FR-027)*

This is the behaviour most likely to surprise someone, so check it deliberately.

1. With four trainees in their four states, sign in as the **instructor**.
2. Publish a **replacement** test into that module.
3. Before it publishes, expect a confirmation naming **how many people will revert**, the count of those currently passed (FR-027).
4. Confirm it.
5. Every trainee's results page now reads **Not started** for that module.
6. Open one trainee's module history, **their old attempts are still listed** (FR-008). They no longer decide the state; they are still visible.

---

## Scenario 6, Presentation *(FR-022, FR-023, FR-024)*

| Check | Expect |
|---|---|
| Results page at 360px | Readable, no sideways scrolling |
| Instructor cohort at 360px | Readable, this is the wider table, so check it carefully |
| Both in **greyscale** | Every state still identifiable, because each badge carries its word (FR-023) |
| A person with no registrations | A clear statement, not an empty table (FR-024) |
| Someone on thirty modules | Page still readable and quick (SC-008) |

For greyscale, use the browser's rendering emulation rather than trusting your eye.

---

## Running the tests

```bash
docker compose exec backend pytest
```

`tests/services/test_state.py` is the one that matters here: a table covering all five states, plus the two cases that catch real mistakes, most-recent-not-best, and attempts at a replaced test not counting.

---

## Done when

- [ ] All six scenarios pass
- [ ] All five states appear correctly for the five set-up trainees
- [ ] A person on 40, 90, 70 with pass mark 80 reads **failed** at **70**
- [ ] Publishing a replacement resets everyone, warns first with a count, and keeps old attempts visible in history
- [ ] No route reaches another person's results
- [ ] No view spans more than one module
- [ ] Every state is legible in greyscale
- [ ] **No table, column, or stored record was added by this phase**
