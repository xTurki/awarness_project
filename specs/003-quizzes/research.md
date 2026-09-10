# Research: Quizzes

**Phase 0 output** for [plan.md](./plan.md). Eight decisions.

No new dependencies were needed. Every decision below is about how to arrange what already exists.

---

## R1, Saving each answer as it is given

**Decision**: Each answer option change posts to `/attempts/{id}/answer` via HTMX, carrying the question id and the selected option ids. The service upserts one row and returns a small fragment confirming it was saved. One request per interaction, no batching.

**Rationale**: FR-018 requires each answer recorded at the moment it is given, independently of the others. An upsert on `(attempt_id, question_id)` means an answer changed five times leaves one row, and a dropped connection loses at most the click in flight.

HTMX is already vendored, so this needs no JavaScript of our own.

**Alternatives considered**: saving the whole form periodically (rejected, a timer means losing up to an interval of work, and "how long is the interval" is a question with no good answer); saving only on navigation between questions (rejected, a trainee who answers and then loses connection without navigating loses that answer); local storage in the browser (rejected, it is a second source of truth, and the point is that the server holds the answers).

---

## R2, Fixing the deadline when the attempt starts

**Decision**: `attempt.ends_at` is computed once at creation as `min(started_at + time_limit, test.closes_at)` and stored. Nothing recomputes it afterwards.

**Rationale**: FR-016 and FR-023 together. Storing rather than computing is what makes the instructor's later edit to the time limit harmless to an attempt already running, there is nothing to recompute because the value was decided when the attempt began. It also makes "how long is left" a subtraction rather than a rule with branches.

**Alternatives considered**: computing from the test on each request (rejected, an instructor editing the limit would change a running attempt's deadline, which FR-016 forbids); storing only `started_at` and the limit (rejected, the closing-time interaction has to be resolved somewhere, and doing it once at the start is cheaper than on every page load).

---

## R3, Fixing the question order

**Decision**: `attempt.question_order` holds the ordered question ids as JSON, written once at creation. Shuffled or not, the attempt is rendered from this list.

**Rationale**: FR-017 requires the same order on every resume. With shuffling on, recomputing would give a different order each time and a trainee returning would see a different test. JSON because MySQL 8 has the type, it is read whole and never searched into, and this is exactly the use the project specification permits it for.

**Alternatives considered**: a join table of attempt-question-position (rejected, a table to hold what is read as one list, always in full); a seeded shuffle recomputed from the attempt id (rejected, clever, and breaks the moment the question set changes; FR-013 makes that impossible, but relying on that is fragile).

---

## R4, Server time is the only time

**Decision**: Every page of an attempt renders `ends_at` as an absolute UTC instant. The countdown is JavaScript that displays the difference. Every write checks `now() < ends_at` on the server before doing anything.

**Rationale**: FR-020 says the device clock is display only. The countdown exists so a trainee can pace themselves; it decides nothing. The server check is what actually enforces the limit, and it is one comparison at the top of each write.

**Alternatives considered**: sending remaining seconds instead of an instant (rejected, it drifts across a slow page load); trusting a submitted "time remaining" from the client (rejected, the client cannot be the timekeeper).

---

## R5, Scoring as a pure function

**Decision**: `scoring.score(questions, answers) -> (points_earned, points_possible)` in its own module. No session, no clock, no I/O. `attempt_service` gathers the rows, calls it, stores the result.

**Rationale**: SC-007 asks for scores verified against worked examples covering single-answer, multi-answer, blank, and fully wrong cases. That is a table-driven test, and a pure function makes it a trivial one. Scoring is also the part of this phase where being wrong is silent, nobody notices a slightly wrong score, so it is worth being the easiest thing to test.

Exact-match, per FR-027: a question's points are earned only when the selected set equals the correct set. Set comparison, one line.

**Alternatives considered**: scoring inside `attempt_service` (rejected, then testing it needs a database and an attempt); scoring in the database (rejected, untestable and unreadable).

---

## R6, Freezing a test once it has been attempted

**Decision**: `test_service` checks for the existence of any attempt before permitting any write to the test, its question list, or the questions in it. One helper, `assert_not_attempted(test_id)`, called at the top of each mutating function.

**Rationale**: FR-013 forbids every kind of change once one attempt exists. A single helper means one rule in one place rather than the same check written eight times. FR-014 requires the refusal to explain itself, so the exception carries a message the template shows directly.

**Alternatives considered**: a boolean `is_frozen` column set on first attempt (rejected, a second source of truth that can drift from whether attempts actually exist); allowing edits and versioning the test (rejected, the owner chose freezing precisely to avoid versions).

---

## R7, Deciding radio versus checkbox

**Decision**: The template counts the options marked correct. One means radio buttons; more than one means checkboxes. The instructor never chooses.

**Rationale**: FR-005 says exactly this, the instructor marks which options are correct, and the presentation follows. It removes a setting, and removes the possibility of a question configured as single-answer while having two correct options.

**Alternatives considered**: an explicit `is_multi` column (rejected, a field that can contradict the options it describes).

---

## R8, Handling the abandoned attempt

**Decision**: No background process. An attempt past its `ends_at` is treated as submitted the next time anyone looks at it, when the trainee returns to it, when their results are listed, or when an instructor opens the attempt list. The transition happens on read.

**Rationale**: FR-022 requires an expired attempt to be scored on what it holds rather than staying open. Doing it on read means no scheduled job, which this phase does not otherwise need, Phase 4 introduces the first one. The trainee sees the correct outcome the moment they look, which is the only moment it matters to them.

**Alternatives considered**: a scheduled sweep (rejected, a whole scheduler for something that can happen on read; that machinery arrives in Phase 4 and is not needed here); leaving them open forever (rejected, FR-022).

---

## Notes for implementation

- **`attempt_number` is derived, not chosen**: count that person's existing attempts at that test and add one. Never taken from the request.
- **A person has at most one attempt in progress per test.** Starting when one is open resumes it rather than creating a second (spec, Assumptions).
- **Submitting twice is a no-op**, not an error (FR-024). The second submit finds the attempt already submitted and returns the same result page.
- **The last write wins for a given question.** Two devices on the same attempt both write to the same row.
