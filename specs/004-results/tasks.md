# Tasks: Results, Where Everyone Stands

**Input**: Design documents from `/specs/004-results/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/routes.md](./contracts/routes.md), [quickstart.md](./quickstart.md)

**Depends on**: Phases 0, 1, and 2 complete, accounts, modules and registrations, tests and attempts. This phase **reads both and writes neither**.

**Tests**: Included. Constitution VI requires them and SC-015 requires every user-facing behaviour covered. `tests/services/test_state.py` carries most of the weight, because the state rule is the whole phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel, different files, no dependency on an unfinished task
- **[Story]**: US1–US4, matching the user stories in spec.md
- Every task names the exact file it touches

## Phase order

Phases follow **priority**, not the numbering in spec.md: US1 (P1), then US2 and US4 (both P2), then US3 (P3). US3 is last because it is the smallest and depends on US1's page existing.

## Path Conventions

Paths follow [plan.md](./plan.md) → Project Structure, continuing the layout of Phases 0, 1, and 2.

---

## Phase 1: Setup

**Purpose**: Almost nothing. This phase adds no dependency, no setting, no volume, and, the point of it, **no table and no column**.

- [ ] T001 Confirm `backend/requirements.txt`, `.env.example`, and `docker-compose.yml` need **no change**, and that no model file is added. Every figure this phase shows already exists in registrations and attempts (FR-025, plan.md → Technical Context)
- [ ] T002 [P] Create the empty files from plan.md → Project Structure: `backend/app/services/results_service.py`, `backend/app/services/state.py`, `backend/app/routers/results.py`, and `backend/app/templates/results/{dashboard,module,cohort}.html`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The one function that decides everything, and the badge that renders it.

**⚠️ CRITICAL**: T003 is the phase. Three call sites use it here and **Phase 4 imports it** to decide who is due, so it takes rows and returns an enum, no session, no clock, no knowledge of who is asking.

- [ ] T003 [P] Write `backend/app/services/state.py`, a `State` enum of exactly five values and `state_for(test, attempts, due_date=None) -> State`, **pure**, evaluated in this order with the first match winning: (1) no test on the module, or it is unpublished → **no test available**; (2) an attempt exists that is not submitted → **in progress**; (3) no submitted attempt **at the currently published test** → **not started**; (4) most recent submitted attempt scored at or above the pass mark → **passed**; (5) otherwise → **failed** (research R1, FR-003). The `due_date` argument is unused in this phase and defaults to `None`. It is reserved so Phase 4 can add *due* and *overdue* by passing a date computed at the call site, `state.py` never learns about registrations, and no caller's signature changes (Phase 4 FR-010)
- [ ] T004 [P] Write `tests/services/test_state.py`, a table covering all five states, plus the two cases that catch real mistakes: a person on **40, then 90, then 70 with a pass mark of 80 is `failed` at 70**, most recent, not best (FR-005); and attempts at a **replaced** test do not count towards state even though they remain in history (FR-008, research R2)
- [ ] T005 [P] Write `backend/app/schemas/results.py`, non-table view objects (`ModuleResultRow`, `AttemptRow`, `CohortRow`) carrying title, state, score, and a link target, so no `table=True` model reaches a template (done-gate 5). **No input model is needed here: this phase exposes no `POST` at all** (FR-025, FR-026)
- [ ] T006 [P] Write `backend/app/templates/components/state_badge.html`, every state renders as a badge carrying **both a colour and its own word**, "Passed", "Failed", "Not started", "In progress", "No test". The word is never dropped in favour of colour and never replaced by an icon (research R5, FR-023)

**Checkpoint**: The rule exists once and is proved across every combination before anything calls it.

---

## Phase 3: User Story 1, See where you stand (Priority: P1) 🎯 MVP

**Goal**: One page listing every module a trainee is on, with their state and score against each. **This page is their dashboard**, not a second list beside it.

**Independent Test**: Register a trainee on four modules, one never attempted, one in progress, one passed, one failed, plus a fifth with no test, and confirm the right state against each.

### Tests for User Story 1

- [ ] T007 [P] [US1] Write `tests/services/test_results_for_person.py`, the list holds exactly the registrations where `role_in_module = 'trainee'`, so a module someone only **instructs** does not appear as training they owe (FR-015); a module with no published test reads **no test available**, never "not started" (FR-006, SC-004); the score shown comes from the deciding attempt **including an instructor's override**, since Phase 2 stores an override in the same column; a removed registration is simply absent (FR-014)
- [ ] T008 [P] [US1] Write `tests/routers/test_results_access.py`, there is **no path parameter for a person anywhere in this phase**, so no route by which one trainee reaches another's results exists to test against; assert the routes that do exist reject any attempt to name someone else (FR-013, SC-005)

### Implementation for User Story 1

- [ ] T009 [US1] Write `for_person(user)` in `backend/app/services/results_service.py`, **one query** joining `registration`, `test`, and `attempt`, ordered so Python groups rows by module in a single pass. Not one query per module: thirty modules must stay quick, and SQLModel's lazy loading makes the slow version the one you get by accident (research R3, SC-008)
- [ ] T010 [US1] Add the ordering rank to `backend/app/services/results_service.py`, sorted **in Python after grouping** so the state rule is never expressed a second time in SQL: failed → not started → in progress → passed → no test available, and within a rank the oldest registration first (research R4, FR-007)
- [ ] T011 [US1] **Move** `GET /` out of `backend/app/routers/dashboard.py` into `backend/app/routers/results.py`, then delete `dashboard.py` once it is empty. The application must register `GET /` **exactly once**, a second registration is shadowed silently, with no error to find. The moved route still serves all three roles: a trainee gets `results/dashboard.html`, because **their dashboard is their results page**, one route, one template, one list, while instructors and administrators keep the `dashboard.html` Phase 0 gave them (FR-001, spec Clarifications)
- [ ] T012 [P] [US1] Write `backend/app/templates/results/dashboard.html`, module title, state badge, score where one exists, and a way in. A person with **no registrations** sees a clear statement, not an empty table (FR-024)
- [ ] T013 [US1] Add the caller's state badge to Phase 1's module home template for `GET /modules/{id}`, a badge on an existing page, not a new route (contracts/routes.md → Where a state is also shown)

**Checkpoint**: A trainee can finally answer "which of these do I still owe?", which is the whole phase.

---

## Phase 4: User Story 2, Look back at one module (Priority: P2)

**Goal**: From the dashboard, open one module and see every attempt made at its test, each leading to the review Phase 2 built.

**Independent Test**: Take a test three times, open the module's history from the dashboard, and confirm all three appear in order with the right scores, each opening its own review.

### Tests for User Story 2

- [ ] T014 [P] [US2] Write `tests/services/test_module_history.py`, the history lists **every** attempt that person made at that module's tests, **including attempts at replaced tests**, which is the one place they remain visible (FR-008, FR-009); a module with no attempts reports that plainly and offers the test where one is available to that person (FR-012); a caller holding no registration on the module gets **404**

### Implementation for User Story 2

- [ ] T015 [US2] Add `history_for(subject, module, actor)` to `backend/app/services/results_service.py`, every attempt with its date, score, and outcome, newest first. **Subject and actor are separate arguments**: a trainee may ask only for themselves, while an instructor may ask for anyone on a module they run, resolved through `module_service.get_for` (FR-009, FR-018, done-gate 6)
- [ ] T016 [US2] Add `GET /results/modules/{id}` to `backend/app/routers/results.py`, refusing with **404** where the caller holds no registration on the module. **This supersedes Phase 2's `GET /tests/{tid}/attempts/mine`**, delete that route and `attempts/list.html` with it, because one page per module covering every test, replaced ones included, is strictly more than one page per test (contracts/routes.md)
- [ ] T017 [P] [US2] Write `backend/app/templates/results/module.html`, date, score, and outcome per attempt, each linking onward
- [ ] T018 [US2] Link each listed attempt to **Phase 2's existing review route** rather than re-implementing a review here (FR-010)

**Checkpoint**: Someone who failed can find out what they got wrong.

---

## Phase 5: User Story 4, See how your people are doing (Priority: P2)

**Goal**: An instructor opens a module they run and sees everyone on it, with those who have not passed first, and is warned, with a number, before publishing a replacement test resets them all.

**Independent Test**: Open a module with five registered people in different states, confirm each state is right, and confirm a module you do not run is refused.

### Tests for User Story 4

- [ ] T019 [P] [US4] Write `tests/services/test_cohort.py`, one row per person registered as a **trainee** on the module, each state decided by the **same `state_for`** the trainee's own page uses (FR-017); those who have not passed come first, then by name within each rank (FR-020); an instructor not assigned to the module is refused **403** (FR-019, SC-012)
- [ ] T020 [P] [US4] Write `tests/services/test_replacement_count.py`, `count_affected_by_replacement(module)` returns exactly the number of registered people currently showing **passed**, computed through the same state function so the number warned about is the number that changes (FR-027, research R6)

### Implementation for User Story 4

- [ ] T021 [US4] Add `for_module(module, actor)` to `backend/app/services/results_service.py`, resolving the module through Phase 1's `module_service.get_for` before anything else, and using **one query** grouped by person (done-gate 6, research R3)
- [ ] T022 [US4] Add `count_affected_by_replacement(module)` to `backend/app/services/results_service.py`, counting through `state_for` rather than a separate rule (research R6)
- [ ] T023 [US4] Add `GET /modules/{id}/results` and `GET /modules/{id}/results/{uid}` to `backend/app/routers/results.py`, both behind `module:write`. The second is **one person's attempt history for that module**, the link every cohort row promises, and the only route by which FR-018 is reachable at all (FR-016, FR-018, contracts/routes.md)
- [ ] T024 [P] [US4] Write `backend/app/templates/results/cohort.html`, name, state badge, score, and a way into that person's attempts. This is the wider of the two tables, so it is the one to check at 360px (FR-016, FR-018)
- [ ] T025 [US4] Wire the confirmation into **Phase 2's** `POST /modules/{id}/tests/{tid}/publish`, when the module already has a published test, show a confirmation first, naming **how many people will revert to "not started"** using T022's count. Phase 2 owns the route; this phase defines what makes the warning necessary (FR-027, SC-014)

**Checkpoint**: The facts the platform has been collecting finally reach somebody who can act on them.

---

## Phase 6: User Story 3, Pick up something unfinished (Priority: P3)

**Goal**: An interrupted attempt is findable again. Phase 2 made it survivable; this makes surviving it useful.

**Independent Test**: Start an attempt, leave it, open the dashboard, and confirm the module reads as in progress and leads back into the same attempt with answers intact.

### Tests for User Story 3

- [ ] T026 [P] [US3] Write `tests/routers/test_in_progress.py`, a module with an unsubmitted attempt reads **in progress**, and following it lands **back in the attempt rather than on a review**, with the answers already given intact (FR-011, SC-007); an attempt whose time ran out reads **passed or failed** on what was answered rather than still in progress, because reading the page triggers Phase 2's expire-on-read

### Implementation for User Story 3

- [ ] T027 [US3] In `backend/app/services/results_service.py`, make the link target for a module in progress resolve to **the attempt itself**, not to its review (FR-011)
- [ ] T028 [US3] Confirm that loading the dashboard triggers Phase 2's expire-on-read path, so a person returning to a lapsed attempt sees its outcome rather than "in progress" (research → Notes for implementation)
- [ ] T029 [US3] In `backend/app/templates/results/module.html`, link an in-progress attempt **into the attempt** while submitted ones link to the review (FR-011)

**Checkpoint**: Nothing a trainee started can be lost by being unfindable.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T030 **Prove the phase's headline claim**: compare `SHOW TABLES` and the column list against the schema Phase 2 left behind, **no table, no column, and no stored record was added** (FR-025, SC-010, quickstart Done when)
- [ ] T031 [P] Check `backend/app/templates/results/dashboard.html` and `cohort.html` at **360px**, including for a person registered on thirty modules, with no sideways page scrolling (FR-022, SC-008)
- [ ] T032 [P] View both pages in **greyscale** using the browser's rendering emulation, not by eye, and confirm every state is still identifiable because each badge carries its word (FR-023, SC-009)
- [ ] T033 Confirm **no view anywhere in this phase spans more than one module**, no route, no template, no aggregate (FR-021, SC-013), and that **this phase adds no `POST` at all**, so there is no way to enter, adjust, or weight a score on these pages (FR-026)
- [ ] T034 Run done-gate 4 as a check: no module under `backend/app/routers/` imports `Session` or `select`
- [ ] T035 Run done-gate 5 as a check: no endpoint or template receives a `table=True` model instance, this phase renders view objects only
- [ ] T036 Confirm `docker compose exec backend pytest` passes against the MySQL container (done-gate 2)
- [ ] T037 Walk all six scenarios in [quickstart.md](./quickstart.md) end to end and tick its **Done when** list, Scenario 5 in particular, which is the behaviour most likely to surprise someone

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: needs Phases 0, 1, and 2 working
- **Foundational (Phase 2)**: needs Setup, **blocks every user story**. T003 is imported by all four
- **US1 (Phase 3)**: needs Foundational. Delivers the MVP
- **US2 (Phase 4)**: needs US1, the history is reached from the dashboard
- **US4 (Phase 5)**: needs Foundational only. It could be built in parallel with US2 by a second person; it shares `state_for` and nothing else
- **US3 (Phase 6)**: needs US1 and US2, it changes where their links point rather than adding a page
- **Polish (Phase 7)**: needs every story you intend to ship

### Within Each Story

Tests first, and they must fail. Then services, then routes, then templates.

### Parallel Opportunities

- T003, T004, T005, T006, the whole foundational layer at once
- T007, T008, both US1 test modules
- T019, T020, both US4 test modules
- **US2 (Phase 4) and US4 (Phase 5) in parallel** once US1 is done, they touch different service functions, different routes, and different templates
- T031, T032, the two presentation checks

---

## Parallel Example: Foundational

```bash
# All four at once, none depends on another:
Task: "backend/app/services/state.py, the five states, first match wins"
Task: "tests/services/test_state.py, all five, plus 40/90/70 and the replaced test"
Task: "backend/app/schemas/results.py, view objects so no table=True reaches a template"
Task: "backend/app/templates/components/state_badge.html, colour and the word, never colour alone"
```

---

## Implementation Strategy

### MVP First

1. Phase 1 → Phase 2 → Phase 3 (US1)
2. **Stop and validate**: quickstart Scenario 1, including the 40/90/70 check
3. A trainee can see where they stand. That is the phase's whole claim, delivered

### Incremental Delivery

US1 → US2 and US4 (in either order, or together) → US3.

### What is easy to get wrong here

This phase is small, and the risk is not complexity, it is **quietly reintroducing what it exists to avoid**:

- **A second rule.** `state_for` is imported by three call sites here and by Phase 4. Any state computed inside a query, a template, or a second helper is a copy that will drift. T003 exists so there is one
- **A stored state.** A `state` column on registration, a cached summary, a results table, each would look like an optimisation and each would go stale the moment an attempt is submitted. T030 is the check that none crept in
- **A query per module.** The obvious loop is thirty modules × three queries, and it works fine with three modules in testing (research R3)
- **Colour carrying meaning.** A badge whose word is dropped for tidiness fails FR-023 silently, since it still looks correct to whoever removed it

### Notes

- Nothing here writes. No score entry, no adjustment, no weighting, correcting a score stays where Phase 2 put it, on the attempt (FR-026)
- Publishing a replacement test resets everyone on the module, including people who passed yesterday. That is deliberate, and T025 is what makes an instructor aware of it before they click
- Commit after each task or logical group
