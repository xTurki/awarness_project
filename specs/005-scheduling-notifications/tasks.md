# Tasks: Scheduling & Notifications

**Input**: Design documents from `/specs/005-scheduling-notifications/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/routes.md](./contracts/routes.md), [quickstart.md](./quickstart.md)

**Depends on**: Phases 0–3 complete. Phase 1 for modules and registrations, Phase 2 for tests and attempts, Phase 3 for the state vocabulary this phase extends and the views those states appear in.

**Tests**: Included. Constitution VI requires them and SC-017 requires every user-facing behaviour covered. Two modules carry the phase: `test_due.py`, because the arithmetic has the most cases, and `test_daily_job.py`, because it runs the job **twice** and asserts nothing happened the second time.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel, different files, no dependency on an unfinished task
- **[Story]**: US1–US4, matching the user stories in spec.md
- Every task names the exact file it touches

## Path Conventions

Paths follow [plan.md](./plan.md) → Project Structure, continuing the layout of Phases 0–3.

---

## Phase 1: Setup

**Purpose**: One dependency and two settings. This is the last phase, and the smallest set-up in the project after Phase 3.

- [ ] T001 Add `APScheduler` to `backend/requirements.txt`, pinned to an exact version, the only new dependency since Phase 1 (plan.md → Technical Context)
- [ ] T002 [P] Extend `backend/app/config.py` with `DUE_SOON_LEAD_DAYS` and `SCHEDULER_HOUR_UTC`. **There is no overdue-reminder interval setting**, an overdue test is announced once and never repeated (spec Clarifications, FR-014)
- [ ] T003 [P] Add `DUE_SOON_LEAD_DAYS=14` and `SCHEDULER_HOUR_UTC=6` to `.env.example`, fourteen days' warning, and a run early enough that anyone due is told before their working day rather than during it (spec Assumptions)
- [ ] T004 [P] Create the empty files from plan.md → Project Structure: `backend/app/models/notification.py`, `backend/app/services/{due,notification_service,daily_job}.py`, `backend/app/routers/notifications.py`, `backend/app/templates/notifications/list.html`, `backend/app/templates/components/nav_badge.html`, and `backend/app/templates/emails/{digest,registered,result}.txt`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: One table, two columns, and the pure function that decides every date in this phase.

**⚠️ CRITICAL**: T007 and T008 come before anything that uses a due date. Getting this arithmetic subtly wrong is the failure mode of the whole phase.

- [ ] T005 [P] Write `backend/app/models/notification.py`, `id` INT PK auto; `user_id` INT FK → `user.id`, **indexed**, not null; `module_id` INT FK → `module.id`, **indexed**, not null (every notification concerns exactly one module); `kind` VARCHAR(20) not null, one of `registered` · `result` · `due_soon` · `overdue`; `due_date` DATE **nullable**, null for `registered` and `result`; `title` VARCHAR(255) not null; `body` TEXT nullable; `created_at` DATETIME not null; `read_at` DATETIME **nullable**, where null means unseen and drives the shell indicator; `emailed_at` DATETIME **nullable**, where null means not yet sent and is what the job selects on. **UNIQUE (user_id, kind, module_id, due_date)**, this single constraint is what makes the job safe to run twice (data-model.md)
- [ ] T006 [P] Add two nullable columns to Phase 2's `backend/app/models/test.py`, `retake_interval_days` INT **nullable** (null means one-off) and `completion_deadline_days` INT **nullable** (null means nobody is chased). If both are set, the interval wins; the form offers one or the other (data-model.md)
- [ ] T007 [P] Write `backend/app/services/due.py`, a pure `due_date_for(test, registration, attempts) -> date | None`. No session, no implicit clock. With an interval: **never passed, attempted or not** → `registration.registered_at + interval`; **most recent attempt passed** → that attempt's `submitted_at + interval`; **most recent attempt did not pass, having passed earlier** → that attempt's `submitted_at`. With a completion period and no interval: passed at any point → `None`; otherwise `registered_at + period`. With neither → `None` (research R1, FR-007, FR-008, FR-009, FR-039)
- [ ] T008 [P] Write `tests/services/test_due.py`, a table over every branch of T007, and in particular: a person registered today on a 90-day module is due in **90 days, not today** (FR-008); an early **failed** attempt does not shorten that first cycle (FR-008); someone who passed and then retook and failed is due from **that failing attempt** (FR-009); and, the assertion that protects FR-014, **no branch ever returns today's date as a moving value**, so an `overdue` row's key does not shift from one morning to the next
- [ ] T009 [P] Write `backend/app/schemas/notification.py`, a non-table `NotificationRead` so the new model never reaches a template (done-gate 5). The only input this phase adds is the two schedule fields, validated through Phase 2's `TestWrite` in T013
- [ ] T010 Recreate the database: `docker compose down -v && docker compose up -d --build`, then `docker compose exec backend python seed.py`. **This is the one phase that genuinely needs the volume dropped**, because it adds two columns to `test`, a table that already exists, and `create_all()` creates missing tables but never alters one (Constitution IV, quickstart Prerequisites)

**Checkpoint**: Every date this phase will act on is computed by one tested function.

---

## Phase 3: User Story 1, Set how often training must be repeated (Priority: P1) 🎯 MVP

**Goal**: An instructor sets a retake interval once, and from then on the platform knows who is due, without them touching it again.

**Independent Test**: Set a module's test to repeat every 90 days, then confirm a person who last passed 91 days ago shows as **overdue** and one who passed yesterday does not.

### Tests for User Story 1

- [ ] T011 [P] [US1] Write `tests/services/test_schedule_validation.py`, a retake interval on a test with **no pass mark** is refused, because a cycle that restarts on passing must know what passing means (FR-003); an interval **shorter than `DUE_SOON_LEAD_DAYS`** is refused, since the warning would fire before the person had taken it (FR-004); a completion period with no pass mark is refused (FR-038); an instructor setting either on a module they do not run is refused (SC-009 pattern); a test with **neither** set generates no due date and no notification, ever (FR-039, SC-016)
- [ ] T012 [P] [US1] Write `tests/services/test_state_due.py`, `state_for` returns **due** and **overdue** only where a due date exists and the person is not currently passed, evaluated after Phase 3's existing five (FR-010, research R2); a person registered **today** on a 90-day module is neither due nor overdue (SC-018); changing the interval re-dates everyone **at once**, with nothing migrated (FR-007, SC-010)

### Implementation for User Story 1

- [ ] T013 [US1] Extend Phase 2's `TestWrite` input model with `retake_interval_days` and `completion_deadline_days`, then accept and validate them in `backend/app/services/test_service.py`, the pass-mark requirement for both, and the interval-versus-warning-period rule. The refusal carries the message the form shows (FR-003, FR-004, FR-038)
- [ ] T014 [US1] Extend Phase 3's `backend/app/services/state.py` with `due` and `overdue`, evaluated **after** the existing five states and decided from the `due_date` argument Phase 3 already reserved. Each call site computes that date with `due.py` and passes it in, so **the signature does not change** and `state.py` stays ignorant of registrations. All three call sites read this one function, and **T015 is what gives each of them a date to pass** (FR-010, research R2)
- [ ] T015 [US1] Pass a due date at every call site in Phase 3's `backend/app/services/results_service.py`, `for_person` and `for_module` already join `registration`, `test`, and `attempt`, so every row holds exactly what `due.py` needs: call it per row and hand the result to `state_for`. Do the same wherever Phase 3 renders the module-home badge. **Without this task the two new states exist in the function and appear on no screen** (FR-010)
- [ ] T016 [US1] Ignore `allowed_attempts` in Phase 2's `backend/app/services/attempt_service.py` whenever `retake_interval_days` is set, a person may retake a recurring test as often as they need until they pass, so that a fixed limit cannot leave them permanently overdue with no way out (FR-005)
- [ ] T017 [US1] Add the two fields to Phase 2's test form template, the form offers **one or the other**, not both (contracts/routes.md, data-model.md)
- [ ] T018 [US1] Show the retake interval to trainees on Phase 2's test detail page, alongside the test's other terms (FR-006)
- [ ] T019 [US1] Extend Phase 3's `backend/app/templates/components/state_badge.html` with the two new states, each carrying **its own word**, "Due", "Overdue", never colour alone (FR-010, Phase 3 research R5)
- [ ] T020 [US1] Confirm the two new states appear in all three places Phase 3's states appear: the trainee's dashboard, the instructor's cohort view, and the **module home page `/modules/{id}`**, the badge Phase 3 added to an existing page, not a separate list (FR-010, Phase 3 contracts)

**Checkpoint**: The platform knows who is due. It has not told anybody yet.

---

## Phase 4: User Story 2, Be told before it lapses, and once it has (Priority: P1)

**Goal**: The first thing the platform does on its own, find who is due, and tell them, with nobody signed in.

**Independent Test**: Set a 90-day interval, arrange a person who passed 76 days ago and one who passed 100 days ago, run the job, and confirm the first is warned it is coming and the second is told it has lapsed.

### Tests for User Story 2

- [ ] T021 [P] [US2] Write `tests/services/test_daily_job.py`, **run the job twice for the same date and assert nothing changed the second time**: no second record, no second message (FR-024, SC-003). A run skipped for several days catches up everyone who became due meanwhile (FR-027, SC-006). A person overdue on **three** modules receives **one** email and gets **three** records (FR-019, FR-034, SC-004). Someone who retakes and passes is not told again, and their next due date is a full interval away (FR-011, SC-005)
- [ ] T022 [P] [US2] Write `tests/services/test_notification_once.py`, an `overdue` notification for a given due date is created **once and never repeated on any later run** (FR-014); a send that fails leaves `emailed_at` **null**, and the next run retries it **without creating a second record** (FR-025, SC-007); a person whose registration is removed stops being due and gets nothing, while notifications already in their list remain (FR-012)

### Implementation for User Story 2

- [ ] T023 [US2] Write `create` in `backend/app/services/notification_service.py`, the record is written **before any message is sent**, and the record is the notification; a message is a delivery of it, never a substitute (FR-021). One record per person per module per event (FR-017)
- [ ] T024 [US2] Write `run_daily(session, today: date) -> RunSummary` in `backend/app/services/daily_job.py` as **one ordinary function taking a session and a date**, the date is a parameter rather than read from the clock, so a test can run it for any day. Steps 1–3: compute each due date through `due.py`, insert `due_soon` where it falls within `DUE_SOON_LEAD_DAYS` and `overdue` where it has passed, and **skip insertions that violate the unique constraint** (contracts/routes.md → The daily job)
- [ ] T025 [US2] Add steps 4–6 to `backend/app/services/daily_job.py`, group each person's **unsent** `due_soon` and `overdue` rows into one email, send it, and stamp `emailed_at` on **every row that message covered**. A failed send leaves them unstamped, which is the whole of FR-025 (FR-019, FR-023)
- [ ] T026 [US2] Make the job a **full sweep** that asks who is due *now* rather than what changed since last time. **No `last_run` record anywhere**, a stored last-run is wrong after a restart, wrong if the clock moves, and wrong if a run half-completed (research R5, R7, FR-027)
- [ ] T027 [P] [US2] Write `backend/app/templates/emails/digest.txt`, one message listing every module due or overdue for that person on that day
- [ ] T028 [US2] Start the scheduler in `backend/app/main.py`'s lifespan, APScheduler's `AsyncIOScheduler`, one cron job at `SCHEDULER_HOUR_UTC`, in the existing `backend` container. **No fourth container, no worker, no broker** (research R6, FR-026, FR-028)
- [ ] T029 [US2] Confirm a **replacement test** notifies everyone it made due on the next run, with no grace period and no suppression, the instructor was warned before publishing what it would do (FR-020, Phase 3 FR-027)

**Checkpoint**: The platform acts without anybody asking it to, and running it twice is harmless.

---

## Phase 5: User Story 3, See what you have been told (Priority: P2)

**Goal**: A record inside the platform, which is what makes a notification something a person can come back to after the email has been filtered, deleted, or missed.

**Independent Test**: Trigger a notification, sign in as that person, and confirm it appears in their list, is marked seen once viewed, and leads to the module it concerns.

### Tests for User Story 3

- [ ] T030 [P] [US3] Write `tests/services/test_notification_list.py`, the list returns the caller's notifications **newest first** (FR-029); opening it stamps `read_at` on everything shown and the indicator stops thereafter (FR-031); a person with none gets a clear statement rather than an empty list (contracts/routes.md → Response conventions)
- [ ] T031 [P] [US3] Write `tests/routers/test_notification_access.py`, **there is no path parameter for a person**, so no route reaches another's notifications; assert the routes that exist refuse any attempt to name someone else (FR-033)

### Implementation for User Story 3

- [ ] T032 [US3] Add `list_for` and `mark_seen` to `backend/app/services/notification_service.py`, both scoped to the caller and nobody else (FR-029, FR-031, FR-033)
- [ ] T033 [US3] Write `backend/app/routers/notifications.py`, `GET /notifications` and `POST /notifications/read`, both behind `auth`, with the **CSRF dependency applied to the POST**. No `Session` or `select` import (done-gate 4, contracts/routes.md, Phase 0 FR-025)
- [ ] T034 [P] [US3] Write `backend/app/templates/notifications/list.html`, each entry says what it concerns and when it arrived, and links to its module. A person overdue on three modules sees **three entries** even though they received one email (FR-032, FR-034)
- [ ] T035 [US3] Write `backend/app/templates/components/nav_badge.html` and render it on every authenticated page, a count of the caller's notifications where `read_at IS NULL` (FR-030)

**Checkpoint**: Email is no longer the only place a notification exists.

---

## Phase 6: User Story 4, Be told when something concerns you (Priority: P3)

**Goal**: Two events that happen inside a request are notified inside that request, not on the next daily run.

**Independent Test**: Register a person onto a module and confirm they are notified at once; have them submit a test and confirm they are notified of the result.

### Tests for User Story 4

- [ ] T036 [P] [US4] Write `tests/services/test_immediate_notifications.py`, registering **five people in one action** notifies each about their **own** registration (FR-015, quickstart Scenario 5); submitting a test notifies the person who submitted, immediately and individually (FR-016, FR-018); neither waits for the daily job

### Implementation for User Story 4

- [ ] T037 [US4] Create a `registered` notification inside Phase 1's `POST /modules/{id}/roster` path, in `backend/app/services/registration_service.py`, one per person registered, created and emailed inline (FR-015, FR-018, research R4)
- [ ] T038 [US4] Create a `result` notification inside Phase 2's submit path, in `backend/app/services/attempt_service.py`, at the moment the attempt is scored (FR-016, FR-018)
- [ ] T039 [P] [US4] Write `backend/app/templates/emails/registered.txt` and `backend/app/templates/emails/result.txt`
- [ ] T040 [US4] Send both through Phase 0's `email_service` in its worker thread, stamping `emailed_at` on success, so a mail failure leaves the record in place with `emailed_at` **null** rather than failing the registration or the submission (FR-023, FR-025, Phase 0 research R8)

**Checkpoint**: The phase is complete, and so is the project's planned scope.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T041 [P] Check `backend/app/templates/notifications/list.html` at **360px**, readable, no sideways page scrolling, and the shell indicator visible without scrolling (FR-040, SC-013)
- [ ] T042 [P] Confirm **due** and **overdue** appear on Phase 3's trainee dashboard and instructor cohort view, and remain legible in **greyscale** (FR-010, Phase 3 FR-023)
- [ ] T043 Confirm the scheduler runs unattended: set `SCHEDULER_HOUR_UTC` a few minutes ahead, restart the backend, and watch the job run with nobody signed in (FR-026, quickstart Scenario 8)
- [ ] T044 Confirm `docker compose ps` shows **the same three containers**, no worker, no broker, no second machine was added (FR-028, SC-016 pattern)
- [ ] T045 Run done-gate 4 as a check: no module under `backend/app/routers/` imports `Session` or `select`
- [ ] T046 Run done-gate 5 as a check: no endpoint or template receives a `table=True` model instance
- [ ] T047 Confirm `docker compose exec backend pytest` passes against the MySQL container (done-gate 2)
- [ ] T048 Walk all nine scenarios in [quickstart.md](./quickstart.md) end to end and tick its **Done when** list, Scenario 3 step 3 in particular, which runs the job a second time for the same date and expects nothing

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: needs Phases 0–3 working
- **Foundational (Phase 2)**: needs Setup, **blocks every user story**
- **US1 (Phase 3)**: needs Foundational. Delivers the MVP, the platform knows who is due
- **US2 (Phase 4)**: needs US1, there is nothing to notify anyone about until a test recurs
- **US3 (Phase 5)**: needs US2 to have created records worth listing, though the list itself can be built against records inserted by hand
- **US4 (Phase 6)**: needs Foundational and `notification_service` from T023 only. It is independent of the daily job entirely, and could be built alongside US3
- **Polish (Phase 7)**: needs every story you intend to ship

### Within Each Story

Tests first, and they must fail. Then models, then services, then routes, then templates.

### Parallel Opportunities

- T002, T003, T004, three different files
- T005, T006, T007, T008, T009, the whole foundational layer at once
- T011, T012, both US1 test modules
- T021, T022, both US2 test modules
- **US3 (Phase 5) and US4 (Phase 6) in parallel** once T023 exists, one is a list, the other two inline calls

---

## Parallel Example: Foundational

```bash
# All five at once, none depends on another:
Task: "backend/app/models/notification.py, the table and its unique constraint"
Task: "backend/app/models/test.py, the two nullable columns"
Task: "backend/app/services/due.py, the pure due-date function"
Task: "tests/services/test_due.py, every branch, plus the newcomer's full first cycle"
Task: "backend/app/schemas/notification.py, the read model"
```

---

## Implementation Strategy

### MVP First

1. Phase 1 → Phase 2 → Phase 3 (US1)
2. **Stop and validate**: someone who passed 91 days ago reads **overdue**, and someone who passed yesterday does not
3. The platform now knows who owes what. Telling them is the next phase, and the harder half

### Incremental Delivery

US1 → US2 → US3 and US4 (in either order, or together).

### What this phase must get right

Most of its requirements exist to stop one thing: **doing it twice**.

- **T024 with T021**, idempotency comes from the **unique constraint**, not from the job remembering anything. Run it twice for the same date and nothing happens. A `last_run` record would look like the obvious solution and would be wrong after a restart, a clock change, or a half-completed run
- **T007 with T008**, every due date is a **fixed calendar date**. If any branch returns "now", the key an `overdue` row is written under moves every morning, and a notification meant to arrive once arrives daily. That is the bug this phase is shaped to prevent
- **T025**, the record exists before the message. A failed send leaves `emailed_at` null and the next run retries; nothing else implements FR-025
- **T014**, the two new states extend Phase 3's one function. Computing them anywhere else is a second copy of the rule

### Notes

- The two new columns on `test` are what force `docker compose down -v` here. New tables alone would not: `create_all()` adds those at startup
- An overdue test is announced **once**. What persists is the state on the dashboard, not repeated messaging, a decision taken while clarifying this phase
- A newcomer gets a **full first interval** from their registration date, so nobody is overdue the morning after they are added
- The design assumes exactly **one `backend` instance**. Two would run two schedulers; the unique constraint makes that wasted work rather than duplicate email, but it is one more place single-instance matters
- Commit after each task or logical group
