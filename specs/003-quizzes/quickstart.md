# Quickstart: Quizzes

**Phase 1 output** for [plan.md](./plan.md). How to prove this phase works.

Each scenario maps to a user story in [spec.md](./spec.md).

---

## Prerequisites

Phases 0 and 1 working — accounts, sign-in, modules with content, people registered on them. You need one published module with an instructor and at least three registered trainees.

```bash
docker compose down -v && docker compose up -d --build   # new tables
docker compose exec backend python seed.py
```

No new settings and no new dependencies in this phase.

---

## Scenario 1 — Build a test *(US1, P1)*

As the **instructor** on your module:

1. Write ten questions. Give one of them two correct options.
2. Confirm the two-correct question renders as **checkboxes** and the others as **radio buttons** — you never chose which (FR-005).
3. Try to save a question with one option, then one with no correct option. Both refused with a message saying what is missing.
4. Assemble a test from the ten, in an order you choose. Set: 20-minute limit, 2 attempts, pass mark 80, shuffling on.
5. Try to publish an empty test — refused (FR-011). Try a pass mark of 150 — refused (FR-012).
6. Publish it. As a trainee, confirm it appears with the limit, attempts, and pass mark shown **before** starting.

---

## Scenario 2 — Take it and get a score *(US2, P1)*

As a registered **trainee**:

1. Start the test. Answer everything. Submit.
2. Score and pass-or-fail appear immediately.
3. Check the arithmetic by hand against what you answered.
4. On the two-correct question, select only one of the two correct options. That question scores **zero** — there is no partial credit (FR-027).
5. Start a second attempt (2 were allowed). Then try a third — refused, and told why.
6. As a trainee **not** registered on the module, request the test directly. Refused.

---

## Scenario 3 — Survive an interruption *(US3, P1)*

This is the one that matters most.

1. Start a fresh attempt. Answer questions 1 through 5.
2. **Kill the browser entirely** — do not submit, do not navigate away.
3. Reopen and return to the attempt.

| Check | Expect |
|---|---|
| Answers 1–5 | All still there |
| Time remaining | Reflects real elapsed time, not a fresh 20 minutes |
| Question order | **Identical** to before, since shuffling is on |

4. Now confirm the deadline is genuinely fixed. With the attempt still open, sign in as the instructor and change the test's time limit to 60 minutes. Back in the attempt: **the deadline has not moved** (FR-016).

> If the deadline moved, `ends_at` is being recomputed instead of read. See research R2.

5. Confirm the server owns the clock: change your computer's system clock forward an hour. The countdown may be wrong; **the attempt does not end early and does not extend** (FR-020).

6. Let an attempt run past its deadline without submitting. Return to it — it is submitted and scored on what was answered (FR-022).

---

## Scenario 4 — Review *(US4, P2)*

As the **trainee**:

1. Open a submitted attempt. Each question shows your answer, whether it was right, and **the correct answer** (FR-031).
2. Open your attempt history — every attempt with its date and score.
3. Confirm that where your result is shown, it is your **most recent** attempt, not your best (FR-029).
4. Request another trainee's attempt directly. Refused.

---

## Scenario 5 — The instructor's view *(US5, P2)*

As the **instructor**:

1. Open the test's attempts. Every trainee's attempts with dates, scores, outcomes.
2. Open one and see the answers that person gave.
3. Override a score. Confirm the trainee now sees the corrected score and that pass-or-fail followed it.
4. Try to override a score on an attempt still in progress — refused (FR-036).
5. Try to open attempts on a module you do not run — refused.

**Then confirm the freeze (FR-013):**

6. Try to edit the test now that people have attempted it. Refused, with a message explaining why (FR-014).
7. Try to reword one of its questions. Also refused.
8. Unpublish it — **this still works**, so you can stop further attempts and build a replacement.

---

## Scenario 6 — On a phone *(FR-037, FR-038, done-gate 3)*

Take a full ten-question test at 360px.

| Check | Expect |
|---|---|
| Answer options | The **whole row** is tappable, not just the small circle |
| Page | No sideways scrolling anywhere |
| Countdown | Visible without scrolling up |
| Long question prompts | Wrap rather than overflow |

Then repeat the instructor screens at 768px and 1280px.

---

## Running the tests

```bash
docker compose exec backend pytest
```

`tests/services/test_scoring.py` deserves the most attention — a table of worked examples covering single-answer, multi-answer, blank, and fully wrong (SC-007). Scoring is the part of this phase where being wrong is silent.

---

## Done when

- [ ] All six scenarios pass
- [ ] An interrupted attempt resumes with every answer, the right remaining time, and the same question order
- [ ] Changing a test's time limit does not move a running attempt's deadline
- [ ] Scores match hand-checked arithmetic across all four worked cases
- [ ] A test that has been attempted cannot be edited by any route
- [ ] A trainee can reach no one else's attempt
- [ ] No module under `app/routers/` imports `Session` or `select`
- [ ] Layout verified at all three widths
