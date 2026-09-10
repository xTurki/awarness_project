# Tasks: Quizzes, Question Banks, Attempts & Scoring

**Input**: Design documents from `/specs/003-quizzes/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/routes.md](./contracts/routes.md), [quickstart.md](./quickstart.md)

**Depends on**: Phases 0 and 1 complete, accounts and sign-in, modules with content, the people registered on them, and `module_service.get_for`. This phase adds no new kind of person and no new way to sign in.

**Tests**: Included. Constitution VI requires them and SC-014 requires every user-facing behaviour covered. Two areas carry most of them: **scoring**, where being wrong is silent, and **the attempt lifecycle**, where being wrong loses somebody's work.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel, different files, no dependency on an unfinished task
- **[Story]**: US1–US5, matching the user stories in spec.md
- Every task names the exact file it touches

## Path Conventions

Paths follow [plan.md](./plan.md) → Project Structure, continuing the layout of Phases 0 and 1.

---

## Phase 1: Setup

**Purpose**: There is almost nothing to set up. This phase adds no dependency, no setting, and no volume.

- [ ] T001 Confirm `backend/requirements.txt` and `.env.example` need **no change** for this phase, nothing new is introduced (plan.md → Technical Context)
- [ ] T002 [P] Create the empty module files from plan.md → Project Structure so the layout is in place before anything is written: `backend/app/models/{question,test,attempt}.py`, `backend/app/services/{question_service,test_service,attempt_service,scoring}.py`, `backend/app/routers/{questions,tests,attempts}.py`, and the template directories `backend/app/templates/{questions,tests,attempts}/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Five tables and the one pure function everything else measures itself against.

**⚠️ CRITICAL**: No user story can begin until this phase is complete.

- [ ] T003 [P] Write `backend/app/models/question.py`, **`question`**: `id` INT PK auto; `module_id` INT FK → `module.id`, **indexed**, not null (the bank belongs to the module, not to a test); `prompt` TEXT not null, plain text; `points` INT not null **default 1**; `position` INT not null; `created_at` DATETIME not null. **`answer_option`**: `id` INT PK auto; `question_id` INT FK → `question.id`, indexed, not null, **cascade delete**; `text` VARCHAR(500) not null; `is_correct` BOOL not null; `position` INT not null. There is **no `type` column**, multiple choice is the only kind (data-model.md)
- [ ] T004 [P] Write `backend/app/models/test.py`, **`test`**: `id` INT PK auto; `module_id` INT FK → `module.id`, indexed, not null; `title` VARCHAR(255) not null; `instructions` TEXT **nullable**, plain text; `is_published` BOOL not null **default false**; `opens_at` DATETIME **nullable** (null = open from the start); `closes_at` DATETIME **nullable** (null = never closes); `time_limit_minutes` INT **nullable** (null = untimed); `allowed_attempts` INT not null **default 1**; `shuffle_questions` BOOL not null **default false**; `passing_score` INT **nullable**, a percentage; `created_at` DATETIME not null. **`test_question`**: `test_id` and `question_id` as a **composite primary key**, plus `position` INT not null. **No `is_frozen` column**, that is derived (research R6)
- [ ] T005 [P] Write `backend/app/models/attempt.py`, **`attempt`**: `id` INT PK auto; `test_id` INT FK → `test.id`, indexed, not null; `user_id` INT FK → `user.id`, indexed, not null; `attempt_number` INT not null, **derived on creation and never supplied by the request**; `started_at` DATETIME not null; `ends_at` DATETIME not null, **fixed at creation** as `min(started_at + limit, closes_at)` and never recomputed (FR-016, FR-023); `submitted_at` DATETIME nullable; `is_submitted` BOOL not null default false; `question_order` **JSON** not null, **fixed at creation**, holding ordered question ids (FR-017); `points_earned`, `points_possible`, `score_percent` INT nullable; `passed` BOOL nullable; `score_overridden` BOOL not null default false. **Index on `(test_id, user_id)`**. **`attempt_answer`**: `id` INT PK auto; `attempt_id` INT FK → `attempt.id`, indexed, not null; `question_id` INT FK → `question.id` not null; `selected_option_ids` **JSON** not null; `is_correct` BOOL nullable; `points_awarded` INT nullable; `answered_at` DATETIME not null. **UNIQUE (attempt_id, question_id)**, this is what makes each save an upsert (data-model.md)
- [ ] T006 [P] Write `backend/app/schemas/quiz.py`, **read models**: non-table `QuestionRead`, `TestRead`, `AttemptRead`, and `AttemptAnswerRead`, so none of the five new `table=True` models reaches a template or a response (done-gate 5). **Input models**: `QuestionWrite` (prompt, points, options, correct), `TestWrite`, `AnswerSubmit` (question id and selected option ids), and `ScoreOverride`, through which every form post is validated, the constitution requires input validated through non-table models. `QuestionRead` must **not** carry `is_correct` when rendered to a trainee taking a test
- [ ] T007 [P] Write `backend/app/services/scoring.py`, one pure function `score(questions, answers) -> (points_earned, points_possible)`. **No session, no clock, no I/O.** A question's points are earned only when the selected option set **exactly equals** the correct set, no partial credit (FR-027). A question with no answer row scores zero (research R5)
- [ ] T008 [P] Write `tests/services/test_scoring.py`, a table of worked examples covering **single-answer, multi-answer, blank, and fully wrong**, plus the partial-selection case that must score zero. This is the test SC-007 asks for, and the one whose failure would otherwise be silent
- [ ] T009 Bring the five new tables into the running database: `docker compose up -d --build`. `create_all()` creates missing tables at startup, so existing modules, pages, and accounts survive. `docker compose down -v` is **not** required here, for the same reason as Phase 1 (Constitution IV)

**Checkpoint**: The tables exist and scoring is provably correct before anything calls it.

---

## Phase 3: User Story 1, Build a test (Priority: P1) 🎯 MVP

**Goal**: An instructor writes questions, assembles a test with a pass mark, and publishes it, and cannot change it once anyone has sat it.

**Independent Test**: Write ten questions, assemble them into a test with a pass mark of 80%, publish it, and confirm a registered trainee can see it with its terms shown before starting.

### Tests for User Story 1

- [ ] T010 [P] [US1] Write `tests/services/test_question.py`, a question with **fewer than two options** is refused; one with **no option marked correct** is refused; both refusals say what is missing (FR-003). An instructor not assigned to the module is refused on every function (FR-006, SC-009)
- [ ] T011 [P] [US1] Write `tests/services/test_test_build.py`, publishing a test with **no questions** is refused (FR-011); a pass mark unreachable with the points available is refused on save (FR-012); once **one attempt exists**, every write to the test, its question list, and its questions is refused, while **publish and unpublish still succeed** (FR-013, FR-014, SC-011)

### Implementation for User Story 1

- [ ] T012 [US1] Write `backend/app/services/question_service.py`, create, edit, and delete questions with their options, validating **at least two options and at least one correct** on save. Every function resolves the module through `module_service.get_for` (FR-001, FR-003, FR-006, done-gate 6). Editing and deleting also call `assert_question_not_attempted(question_id)`, one query joining `test_question` to `attempt`, because a question inside an **attempted** test is frozen too, and `assert_not_attempted(test_id)` in T013 cannot see it from here (FR-013, SC-011, contracts/routes.md)
- [ ] T013 [US1] Write `backend/app/services/test_service.py` with `assert_not_attempted(test_id)` at the top of **every** mutating function, one helper, one rule, checking whether any attempt row exists rather than reading a flag. The exception it raises carries the message the template shows (research R6, FR-013, FR-014)
- [ ] T014 [US1] Add test assembly to `backend/app/services/test_service.py`, create and update a test from selected bank questions in the instructor's chosen order, writing `test_question` rows; refuse an unreachable pass mark; refuse publishing with no questions (FR-007, FR-011, FR-012)
- [ ] T015 [US1] Write `backend/app/routers/questions.py`, the six question-bank routes from contracts/routes.md, all behind `module:write`. No `Session` or `select` import (done-gate 4)
- [ ] T016 [US1] Write `backend/app/routers/tests.py`, `GET /modules/{id}/tests` (instructors see all, trainees see published ones inside their window), `GET/POST` new and edit, `POST .../publish`, and `GET /modules/{id}/tests/{tid}` showing a trainee the **time limit, attempts allowed, and pass mark before they start** (FR-009, FR-010)
- [ ] T017 [P] [US1] Write `backend/app/templates/questions/list.html` and `backend/app/templates/questions/form.html`, options with a correct-marker each; the form states what is required before it refuses
- [ ] T018 [P] [US1] Write `backend/app/templates/tests/list.html`, `backend/app/templates/tests/form.html`, and `backend/app/templates/tests/detail.html`, the form renders **read-only with the reason** when the test is frozen (FR-014)
- [ ] T019 [US1] Apply the CSRF dependency to every POST in `backend/app/routers/questions.py` and `backend/app/routers/tests.py`

**Checkpoint**: A real test exists and a trainee can see it. Nobody can take it yet.

---

## Phase 4: User Story 2, Take a test and know the result (Priority: P1)

**Goal**: A trainee starts a test, answers on one scrolling page, submits, and is told their score and outcome at once.

**Independent Test**: Take a ten-question test, submit it, and confirm the score and pass-or-fail appear immediately and match the answers given.

### Tests for User Story 2

- [ ] T020 [P] [US2] Write `tests/services/test_attempt_start.py`, an attempt begins only when the test is **published**, the person holds a registration, the current time is **inside the window**, and attempts remain (FR-015). `attempt_number` is derived by counting that person's existing attempts and adding one, **never taken from the request**. Starting while one is already in progress **resumes it** rather than creating a second (research R8 notes)
- [ ] T021 [P] [US2] Write `tests/services/test_attempt_submit.py`, submission scores through `scoring.score`, sets `score_percent`, and sets `passed` against the test's pass mark (FR-026, FR-028); a **second submission is ignored** and returns the same result (FR-024); an attempt with every answer blank submits and scores **zero** (spec Edge Cases)
- [ ] T022 [P] [US2] Write `tests/routers/test_attempt_access.py`, a trainee not registered on the module is refused the test (FR-015); a trainee beyond the permitted attempts is refused **and told how many were allowed** (FR-025, SC-010); and a trainee who has read **none** of the module's pages can still start the test, since reading is never a precondition (FR-039, Phase 1 FR-035); and an **unpublished** test is absent from a trainee's test list entirely, not merely refused when started (FR-010)

### Implementation for User Story 2

- [ ] T023 [US2] Write the start half of `backend/app/services/attempt_service.py`, resolve the module through `module_service.get_for` first (done-gate 6), check the four conditions, derive `attempt_number`, and **fix `ends_at` and `question_order` at creation**. `ends_at` is `min(started_at + time_limit, closes_at)`; `question_order` is the test's question ids, shuffled only if `shuffle_questions` is set (research R2, R3)
- [ ] T024 [US2] Add `save_answer` to `backend/app/services/attempt_service.py`, an **upsert on `(attempt_id, question_id)`**, so an answer changed five times leaves one row and the last write for a question wins across two devices (FR-018, research R1)
- [ ] T025 [US2] Add `submit` to `backend/app/services/attempt_service.py`, gather the rows, call `scoring.score`, store `points_earned`, `points_possible`, `score_percent`, and `passed`; a second call returns the existing result unchanged (FR-024, FR-026)
- [ ] T026 [US2] Write `backend/app/routers/attempts.py`, `POST /tests/{tid}/attempts`, `GET /attempts/{aid}`, `POST /attempts/{aid}/answer`, `POST /attempts/{aid}/submit`. The answer route does **one upsert and returns a small fragment**, it is the only high-traffic route in the platform (contracts/routes.md, research R1)
- [ ] T027 [US2] Write `backend/app/templates/attempts/take.html`, **one scrolling page**: every question at once in the attempt's fixed order, submit at the end, no per-question navigation and no separate review screen (spec Clarifications). Each option posts its change over HTMX to the answer route
- [ ] T028 [US2] Render each question in `backend/app/templates/attempts/take.html` as **radio buttons when exactly one option is correct and checkboxes when more than one is**, counted from the options, never chosen by the instructor (FR-005, research R7)
- [ ] T029 [US2] Render the score and pass-or-fail in `backend/app/templates/attempts/review.html`, reached by redirect from the submit route, so both appear immediately after submission and within two seconds (SC-002, FR-028)
- [ ] T030 [US2] Apply the CSRF dependency to every POST in `backend/app/routers/attempts.py`

**Checkpoint**: The phase's centre works, somebody takes a test and learns their result.

---

## Phase 5: User Story 3, Survive an interruption (Priority: P1)

**Goal**: A dropped connection, a locked phone, or a closed tab costs at most the click in flight.

**Independent Test**: Start an attempt, answer several questions, kill the browser, reopen, and confirm every answer is still there, the order is unchanged, and the remaining time reflects real elapsed time.

### Tests for User Story 3

- [ ] T031 [P] [US3] Write `tests/services/test_attempt_resume.py`, a resumed attempt returns **every answer already given** (FR-019); its `question_order` is **byte-identical** to the first render (FR-017, SC-005); and changing the test's `time_limit_minutes` while the attempt is open **does not move `ends_at`** (FR-016), the test that proves the deadline is stored rather than recomputed. Cover the other branch of `min()` too: an attempt started five minutes before `closes_at` with a twenty-minute limit ends at **`closes_at`**, not twenty minutes later (FR-023)
- [ ] T032 [P] [US3] Write `tests/services/test_attempt_expiry.py`, `save_answer` after `ends_at` is **refused** (FR-021, SC-006); an attempt read after `ends_at` is treated as **submitted and scored on what it holds**, with no scheduled job involved (FR-022, research R8); an abandoned attempt never stays open indefinitely

### Implementation for User Story 3

- [ ] T033 [US3] Add the `now() < ends_at` check at the top of every write in `backend/app/services/attempt_service.py`, using the **server clock only**. Anything the browser reports about time is display (FR-020, FR-021, research R4)
- [ ] T034 [US3] Add expire-on-read to `backend/app/services/attempt_service.py`, an attempt found past `ends_at` is submitted and scored the moment anyone looks at it: the trainee returning, their result list, or an instructor's attempt list. **No background process** (FR-022, research R8)
- [ ] T035 [US3] Render the attempt in `backend/app/templates/attempts/take.html` from `question_order` and the stored answers, so a resumed attempt is indistinguishable from an uninterrupted one (FR-017, FR-019)
- [ ] T036 [US3] Send `ends_at` to `backend/app/templates/attempts/take.html` as an **absolute UTC instant** and let the countdown display the difference. The countdown decides nothing; it stays visible while scrolling (research R4, spec Clarifications)

**Checkpoint**: The failure that would stop the platform being used twice is handled.

---

## Phase 6: User Story 4, Look back at what you did (Priority: P2)

**Goal**: A trainee sees what they answered, what was right, what the right answer was, and how they did across attempts.

**Independent Test**: Complete an attempt, open its review, and confirm the trainee sees their own answers and result, and cannot see anyone else's.

### Tests for User Story 4

- [ ] T037 [P] [US4] Write `tests/routers/test_review_access.py`, a trainee requesting **another person's attempt** is refused with 404 (FR-032, SC-008); opening the review of an attempt **still in progress** returns them to the attempt rather than a partial result (spec US4)
- [ ] T038 [P] [US4] Write `tests/services/test_most_recent_attempt.py`, a trainee who scored 40, then 90, then 70 is represented by **70**, the most recent, with all three still in their history (FR-029). Phases 3 and 4 both read this rule

### Implementation for User Story 4

- [ ] T039 [US4] Add two routes to `backend/app/routers/attempts.py`: `GET /attempts/{aid}/review` behind `attempt:view`, redirecting into the attempt while it is in progress; and `GET /tests/{tid}/attempts/mine` behind `auth`, rendering the caller's **own** attempts at that test, this is the route T042's template needs, and without it FR-030 has no way in. Phase 3 replaces it with `/results/modules/{id}` and deletes both (contracts/routes.md)
- [ ] T040 [US4] Add a most-recent-submitted-attempt query to `backend/app/services/attempt_service.py`, using the `(test_id, user_id)` index. **Most recent, not best**, Phases 3 and 4 read this and must not each write their own (FR-029)
- [ ] T041 [P] [US4] Write `backend/app/templates/attempts/review.html`, each question with the answer given, whether it was right, and **the correct answer** (FR-031)
- [ ] T042 [P] [US4] Write `backend/app/templates/attempts/list.html`, the trainee's attempts at a test, each with its date, score, and outcome (FR-030)

**Checkpoint**: A trainee learns something from the test, not only a number.

---

## Phase 7: User Story 5, Check on the people taking it (Priority: P2)

**Goal**: An instructor sees the attempts on their test and can correct a score by hand when a question turns out to have been unfair.

**Independent Test**: View the attempts on your own test, change one attempt's score, and confirm the new score and its outcome are what the trainee now sees.

### Tests for User Story 5

- [ ] T043 [P] [US5] Write `tests/services/test_score_override.py`, an override replaces `score_percent`, sets `score_overridden` true, and **recomputes `passed` from the new score** (FR-035); an override on an **unsubmitted** attempt is refused (FR-036); an instructor not assigned to the module is refused (FR-034, SC-009)

### Implementation for User Story 5

- [ ] T044 [US5] Add `list_attempts_for_test` and `override_score` to `backend/app/services/attempt_service.py`, both resolving the module through `module_service.get_for` before anything else (done-gate 6, FR-033, FR-035)
- [ ] T045 [US5] Add `GET /tests/{tid}/attempts` and `POST /attempts/{aid}/score` to `backend/app/routers/attempts.py`, both behind `module:write` (contracts/routes.md)
- [ ] T046 [P] [US5] Write `backend/app/templates/attempts/cohort.html`, every attempt on the test with who, when, score, and outcome, each linking to that attempt's answers (FR-033)
- [ ] T047 [US5] Show an overridden score to the trainee in `backend/app/templates/attempts/review.html` and `backend/app/templates/attempts/list.html`, so the corrected figure is the one they see wherever their result appears (FR-035, quickstart Scenario 5)

**Checkpoint**: An automatically scored test now has a human override, which is what makes automatic scoring safe to rely on.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T048 [P] Take a full ten-question test at **360px** in `backend/app/templates/attempts/take.html`, the **whole answer row is tappable**, not only the small control beside it; long prompts wrap; the countdown stays visible without scrolling up (FR-037, FR-038, SC-013)
- [ ] T049 [P] Walk the instructor screens, question form, test form, attempt list, at 768px and 1280px (SC-012, done-gate 3)
- [ ] T050 Run done-gate 4 as a check: no module under `backend/app/routers/` imports `Session` or `select`
- [ ] T051 Run done-gate 5 as a check: no endpoint or template receives a `table=True` model instance, and in particular that a trainee taking a test never receives `is_correct`
- [ ] T052 Run done-gate 6 as a check: every module-scoped function in `question_service`, `test_service`, and `attempt_service` resolves through `module_service.get_for`
- [ ] T053 Confirm `docker compose exec backend pytest` passes against the MySQL container (done-gate 2)
- [ ] T054 Walk all six scenarios in [quickstart.md](./quickstart.md) end to end and tick its **Done when** list, including the deadline check in Scenario 3 step 4, which is the one that proves `ends_at` is stored rather than recomputed

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: needs Phases 0 and 1 working
- **Foundational (Phase 2)**: needs Setup, **blocks every user story**
- **US1 (Phase 3)**: needs Foundational. Delivers the MVP
- **US2 (Phase 4)**: needs US1, nothing can be taken until something is built
- **US3 (Phase 5)**: needs US2. It **hardens** the attempt US2 creates rather than adding a separate feature: the answer-upsert route is built in T024 and T026 because there is no way to answer at all without it, and US3 then adds resumption, the fixed deadline, the server clock, and expiry
- **US4 (Phase 6)**: needs US2, there is nothing to review until an attempt is submitted
- **US5 (Phase 7)**: needs US2 and US4. Independent of US3
- **Polish (Phase 8)**: needs every story you intend to ship

### Within Each Story

Tests first, and they must fail. Then models, then services, then routers, then templates.

### Parallel Opportunities

- T003, T004, T005, T006, T007, T008, the whole foundational layer at once
- T010, T011, both US1 test modules
- T020, T021, T022, all three US2 test modules
- T031, T032, both US3 test modules
- T017 and T018; T041 and T042, template groups

---

## Parallel Example: User Story 2

```bash
# The three test modules first, all must fail before anything below is written:
Task: "tests/services/test_attempt_start.py, the four start conditions and derived attempt_number"
Task: "tests/services/test_attempt_submit.py, scoring, double submit, all-blank"
Task: "tests/routers/test_attempt_access.py, unregistered refused, attempts exhausted refused"
```

---

## Implementation Strategy

### MVP First

1. Phase 1 → Phase 2 → Phase 3 (US1)
2. **Stop and validate**: quickstart Scenario 1, including the checkbox-versus-radio check you never configured
3. A real test exists on a real module. Nobody can sit it yet, but it is demonstrable

### Incremental Delivery

US1 → US2 → US3 → US4 → US5, validating the matching quickstart scenario after each.

### The four things this phase must get right

Everything else here is forms and queries. These are not:

1. **T024, each answer is its own write.** A dropped connection loses the click in flight and nothing more
2. **T023, `ends_at` and `question_order` are fixed at creation.** Stored, never recomputed. T031 is the test that proves it, by changing the time limit mid-attempt and asserting the deadline did not move
3. **T033, the server owns the clock.** The countdown is decoration
4. **T007 with T008, scoring is a pure function with a table of worked examples.** It is the one place where being wrong produces no error, no crash, and no complaint, just a wrong result nobody notices

### Notes

- Five new tables need only `docker compose up -d --build`. No column on an existing table changes, so nothing is dropped
- A test is frozen from its first attempt. That is deliberate and is what lets old attempts keep their meaning, the test that produced them never changed
- Commit after each task or logical group
