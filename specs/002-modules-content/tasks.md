# Tasks: Modules, Content & Registration

**Input**: Design documents from `/specs/002-modules-content/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/routes.md](./contracts/routes.md), [quickstart.md](./quickstart.md)

**Depends on**: Phase 0 (`specs/001-platform-foundation`) complete and working — accounts, sign-in, the shell. This phase adds no new way to sign in and no new kind of person.

**Tests**: Included. Constitution VI requires them, FR-036 (Phase 0) requires one command to run them, and SC-014 requires every user-facing behaviour covered. `tests/services/test_sanitise.py` is the one whose failure would be silent in production.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel — different files, no dependency on an unfinished task
- **[Story]**: US1–US4, matching the user stories in spec.md
- Every task names the exact file it touches

## Path Conventions

Paths follow [plan.md](./plan.md) → Project Structure, continuing Phase 0's layout: `backend/app/` for the application, `tests/` at the repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: The two new dependencies, the upload volume, and the one setting both upload limits derive from.

- [ ] T001 Add `nh3` to `backend/requirements.txt`, pinned to an exact version (research R2 — `bleach` is deprecated and is not the choice here)
- [ ] T002 [P] Vendor Quill into `backend/app/static/vendor/quill/` as committed files — never a CDN reference, because this editor runs on the page where content every trainee reads is authored (research R7)
- [ ] T003 [P] Extend `backend/app/config.py` with `UPLOAD_MAX_MB`, `UPLOAD_DIR`, and `ALLOWED_IMAGE_EXTENSIONS` = `.png .jpg .jpeg .gif .webp` (research R3)
- [ ] T004 [P] Add `UPLOAD_MAX_MB=5` to `.env.example` — five megabytes per image, comfortably more than a screenshot needs (spec Assumptions)
- [ ] T005 Extend `docker-compose.yml` with a second named volume for uploads, mounted read-write into `backend` at `/data/uploads` and **read-only** into `nginx`
- [ ] T006 Turn `nginx/nginx.conf` into a template rendered at container start, with `client_max_body_size` derived from `UPLOAD_MAX_MB` plus a small multipart margin, and a `/uploads/` location serving that volume as static content. **One variable feeds both limits** so they cannot drift apart (research R4)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Four tables, the sanitiser, the single authorisation chokepoint, and the module navigation every later phase renders inside.

**⚠️ CRITICAL**: No user story can begin until this phase is complete. T013 in particular is what every module-scoped action in this phase and in Phases 2–4 calls.

- [ ] T007 [P] Write `backend/app/models/module.py` — `id` INT PK auto; `title` VARCHAR(255) not null (**no code or reference number** — the title identifies it, FR-001); `description` TEXT **nullable**; `is_published` BOOL not null **default false**; `created_at` DATETIME not null; `deleted_at` DATETIME **nullable**, where `NULL` means live (FR-010). There is **no `archived` state** (data-model.md → `module`)
- [ ] T008 [P] Write `backend/app/models/page.py` — `id` INT PK auto; `module_id` INT FK → `module.id`, **indexed**, not null; `title` VARCHAR(255) not null; `body` **MEDIUMTEXT** not null — `TEXT` would truncate at 64KB **silently** (research R6, FR-017); `position` INT not null, **unique within `module_id`**; `is_published` BOOL not null **default false** so a page starts as a draft (FR-012); `created_at` and `updated_at` DATETIME not null
- [ ] T009 [P] Write `backend/app/models/content_image.py` — `id` INT PK auto; `module_id` INT FK → `module.id`, indexed, not null; `stored_name` VARCHAR(64) not null, holding `uuid4().hex` plus the normalised extension and **never derived from what was uploaded**; `original_name` VARCHAR(255) not null, **for display only, never used to build a path**; `content_type` VARCHAR(100) not null, recorded but not trusted; `size_bytes` INT not null; `uploaded_by` INT FK → `user.id` not null; `uploaded_at` DATETIME not null (research R3)
- [ ] T010 [P] Write `backend/app/models/registration.py` — `id` INT PK auto; `user_id` INT FK → `user.id`, indexed, not null; `module_id` INT FK → `module.id`, indexed, not null; `role_in_module` VARCHAR(20) not null, one of `instructor` · `trainee`, **independent of `user.role`** (FR-026); `registered_at` DATETIME not null; **UNIQUE (user_id, module_id)**, which is what makes FR-027 a database guarantee. **No status column** — a registration exists or the person is not on the module (FR-030)
- [ ] T011 [P] Write `backend/app/sanitise.py` — one allowlist and one function. Tags: `p br h2 h3 h4 strong em u ul ol li a blockquote code pre img`. Attributes: `href` on `a` with schemes **`http`, `https`, `mailto` only**; `src alt title width` on `img`. Everything else stripped, including `style`, every `on*` handler, `script`, `iframe`, `object`, `embed`, `form`. Kept out of `content_service` deliberately so it has its own test module (research R2)
- [ ] T012 [P] Write `tests/services/test_sanitise.py` — a `<script>` tag, an `on*` handler, a `javascript:` href, a `style` attribute, and `iframe`/`object`/`embed`/`form` are each removed; allowed headings, emphasis, lists, and links survive unchanged
- [ ] T013 Write `backend/app/services/module_service.py` with `get_for(module_id, actor)` — the **single chokepoint** every module-scoped action resolves through. Returns the module or raises `NotFound`; it never returns "found but forbidden", because that would disclose that the module exists. Administrator: every module in any state. Instructor: modules they are assigned to, **including unpublished**. Trainee: **published** modules they hold a registration on. A soft-deleted module is invisible to everyone (research R1, FR-009)
- [ ] T014 [P] Write `tests/services/test_module_access.py` — the full matrix for `get_for`: three actor kinds × published/unpublished/soft-deleted × assigned/registered/neither. This is the test that proves FR-009, SC-006, and SC-007
- [ ] T015 [P] Write `backend/app/schemas/module.py` — **read models**: non-table `ModuleRead`, `PageRead`, and `RegistrationRead`, so that none of the four new `table=True` models ever reaches a template or a response (done-gate 5). **Input models**: `ModuleWrite`, `PageWrite`, `PageReorder`, and `RosterAdd`, through which every form post in this phase is validated before it reaches a service — the constitution requires input validated through non-table models, because SQLModel does not validate table classes
- [ ] T016 [P] Write `backend/app/templates/components/module_nav.html` — **one** markup block: Bootstrap offcanvas below 992px, a persistent column above it, the two behaviours from CSS alone. Phases 2, 3, and 4 all render inside this (research R9, FR-033)
- [ ] T017 Bring the four new tables into the running database: `docker compose up -d --build`. `create_all()` creates missing tables at startup, so the four appear and **existing accounts survive**. `docker compose down -v` is **not** required here: it is required only when a column changes on a table that already exists, and this phase changes none (Constitution IV)

**Checkpoint**: Tables exist, HTML cannot be stored unsanitised, and one function decides who may see a module.

---

## Phase 3: User Story 1 — Set up a module and put someone in charge of it (Priority: P1) 🎯 MVP

**Goal**: An administrator creates a module and assigns an instructor. Nobody else sees it until it is published.

**Independent Test**: As an administrator, create a module and assign an instructor; confirm that instructor now sees it in their list while a trainee does not and cannot reach it by address.

### Tests for User Story 1

- [ ] T018 [P] [US1] Write `tests/services/test_module_admin.py` — create, publish, unpublish, soft-delete, and restore each refuse an instructor and a trainee and succeed for an administrator (FR-005); soft-delete leaves pages, images, and registrations untouched and restore returns them (SC-012); unpublishing and then publishing again returns the module to trainees with its pages, images, and registrations unchanged (SC-013)
- [ ] T019 [P] [US1] Write `tests/routers/test_module_visibility.py` — an unpublished module returns **404** to a trainee requesting its address directly, and 200 to the assigned instructor (FR-007, quickstart Scenario 1)

### Implementation for User Story 1

- [ ] T020 [US1] Add `create`, `update`, `set_published`, `soft_delete`, and `restore` to `backend/app/services/module_service.py`, each taking the acting account and verifying it is an administrator (Principle III, done-gate 6)
- [ ] T021 [US1] Add `assign_instructor` and `remove_instructor` to `backend/app/services/module_service.py`, writing and deleting `registration` rows with `role_in_module = "instructor"`. A module with **no** instructor is permitted (FR-004, contracts/routes.md)
- [ ] T022 [US1] Write `backend/app/routers/modules.py` — `GET /modules`, `GET /modules/new`, `POST /modules`, `GET /modules/{id}/edit`, `POST /modules/{id}`, `POST /modules/{id}/publish`, `POST /modules/{id}/delete`, `POST /modules/{id}/restore`, `POST /modules/{id}/instructors`, `POST /modules/{id}/instructors/{uid}/remove`. There is **no permanent-delete route**. This module must not import `Session` or `select` (done-gate 4)
- [ ] T023 [P] [US1] Write `backend/app/templates/modules/list.html` — the list differs by role, which is the point: every module for an administrator, assigned ones for an instructor, registered published ones for a trainee (FR-006, FR-007, FR-008)
- [ ] T024 [P] [US1] Write `backend/app/templates/modules/form.html` — title and description, for both create and edit
- [ ] T025 [US1] Apply the CSRF dependency to every POST in `backend/app/routers/modules.py` (Phase 0 research R3)

**Checkpoint**: Modules exist and have owners. There is nothing in them yet.

---

## Phase 4: User Story 2 — Write the module's material (Priority: P1)

**Goal**: Ordered pages with real formatting, drafts alongside published ones, images inside them — and a body column that cannot hold anything unsafe.

**Independent Test**: Write three pages, reorder them, leave one a draft, put an image in another, and confirm a registered trainee sees exactly the two published pages in the chosen order with the image visible.

### Tests for User Story 2

- [ ] T026 [P] [US2] Write `tests/services/test_content.py` — a new page is created as a **draft positioned last**; reorder rewrites positions in one transaction and keeps them unique within the module; publishing and unpublishing act on one page alone; a body of **five thousand words** is stored and read back with no loss (FR-012, FR-013, SC-011)
- [ ] T027 [P] [US2] Write `tests/services/test_content_sanitising.py` — submit a body containing `<script>`, an `on*` handler, and a `javascript:` link, then assert on **the stored column** that they are absent. Asserting on the rendered page would pass even if the sanitiser were in the wrong place (FR-016, SC-004)
- [ ] T028 [P] [US2] Write `tests/routers/test_content_access.py` — an instructor assigned to a *different* module receives **403** on every page route here; a trainee receives **404** for a draft page (FR-018, SC-005, SC-007)
- [ ] T029 [P] [US2] Write `tests/services/test_upload.py` — an extension outside the allowlist is refused; a file over the cap is refused; `stored_name` is generated and **never** derived from `original_name`, so `../../app/main.py` as a filename cannot decide where the file lands; and an `.exe` renamed `.png` **is accepted**, which is the recorded decision, not a defect (research R3). Assert also that **no upload route is reachable by a trainee at all**, and none accepts a non-image (FR-020)

### Implementation for User Story 2

- [ ] T030 [US2] Write the page half of `backend/app/services/content_service.py` — create, update, publish, and delete, **calling `sanitise` before every write of `body`** and never after. New pages go last. `updated_at` is stamped on each save; concurrent edits are last-write-wins with no warning (FR-016, research R5, spec Assumptions)
- [ ] T031 [US2] Add `reorder` to `backend/app/services/content_service.py` — rewrite the affected positions in **one transaction**, preserving uniqueness within the module (research R5, FR-013)
- [ ] T032 [US2] Add `save_image` to `backend/app/services/content_service.py`, taking **file bytes and a filename — not an `UploadFile`** (Principle II). It checks the extension against the allowlist and the size against the cap, generates `uuid4().hex` plus the normalised extension, writes into `UPLOAD_DIR`, and inserts the `content_image` row (research R3, FR-019, FR-021)
- [ ] T033 [US2] Write `backend/app/routers/content.py` — the nine page routes and `POST /modules/{id}/images` from contracts/routes.md. The router reads the upload off the request and hands **bytes** to the service; no file handling lives here (Principle I, plan.md Constitution Check)
- [ ] T034 [P] [US2] Write `backend/app/templates/modules/page_form.html` — Quill wired to the vendored asset, producing headings, emphasis, lists, and links **without the instructor typing markup** (FR-015, research R7)
- [ ] T035 [P] [US2] Write `backend/app/templates/modules/page_list.html` — the instructor's list, drafts included, in position order, with reorder controls (contracts/routes.md)
- [ ] T036 [US2] Reject an oversized or wrong-type upload in `backend/app/routers/content.py` by returning to the editor with a message **naming the limit or the accepted types** — never a blank error page (FR-021, quickstart Scenario 5)
- [ ] T037 [US2] Verify the two limits agree: upload a file just over `UPLOAD_MAX_MB` and confirm the **application's** message appears rather than a bare Nginx 413 (research R4)
- [ ] T038 [US2] Apply the CSRF dependency to every POST in `backend/app/routers/content.py`

**Checkpoint**: A module has real material. Nothing unsafe can be in the `body` column, which is provable by looking at the column.

---

## Phase 5: User Story 3 — Put people on a module (Priority: P2)

**Goal**: People are put on modules by an administrator or the module's instructor — several at once — and taken off the same way. Never by themselves.

**Independent Test**: Register five trainees in one action, confirm all five see the module, remove one, and confirm that person no longer sees it while the other four do.

### Tests for User Story 3

- [ ] T039 [P] [US3] Write `tests/services/test_registration.py` — five people registered in **one transaction**; someone already registered is **skipped silently**, with no duplicate row and no error raised (FR-027, research R8); the `UNIQUE (user_id, module_id)` constraint refuses a duplicate at the database level even if the service check were bypassed; removal deletes the row
- [ ] T040 [P] [US3] Write `tests/routers/test_no_self_registration.py` — no route in the application registers or deregisters the acting person on their own behalf, and no template links to one (FR-028, SC-010)

### Implementation for User Story 3

- [ ] T041 [US3] Write `backend/app/services/registration_service.py` — `register_many`, `remove`, and `roster`, each resolving the module through `module_service.get_for` rather than querying by id (research R1, done-gate 6). An instructor may register trainees on modules they are assigned to; an administrator may register anyone on anything (FR-023, FR-024)
- [ ] T042 [US3] Write `backend/app/routers/registrations.py` — `GET /modules/{id}/roster`, `POST /modules/{id}/roster`, `POST /modules/{id}/roster/{uid}/remove`, all behind `module:write` (FR-029)
- [ ] T043 [P] [US3] Write `backend/app/templates/modules/roster.html` — everyone registered with their capacity, plus a **multi-select of existing accounts** submitted as one form. Not a file import (research R8, FR-025)
- [ ] T044 [US3] Apply the CSRF dependency to every POST in `backend/app/routers/registrations.py`

**Checkpoint**: A written module is now training that named people are expected to do.

---

## Phase 6: User Story 4 — Find and read your training (Priority: P2)

**Goal**: A trainee signs in, sees what they are on, opens it, and reads it on whatever device they have.

**Independent Test**: As a registered trainee, sign in, open a module from the dashboard, and read its published pages in order on a phone and on a desktop.

### Tests for User Story 4

- [ ] T045 [P] [US4] Write `tests/routers/test_trainee_reading.py` — the dashboard lists exactly the modules the trainee holds a registration on and no others (FR-031); an unregistered module is **404**; a draft page is **404**; published pages appear in the instructor's order (FR-014, SC-005, SC-006)

### Implementation for User Story 4

- [ ] T046 [US4] Extend `backend/app/routers/dashboard.py` so a trainee's dashboard lists their registered modules. **This is the same page Phase 3 will extend with a state against each module — do not build a second list** (FR-031, spec Clarifications)
- [ ] T047 [US4] Add `GET /modules/{id}` and `GET /modules/{id}/pages/{pid}` to `backend/app/routers/modules.py` and `backend/app/routers/content.py` respectively, both behind `module:read`, showing published pages in `position` order (FR-032, FR-014)
- [ ] T048 [P] [US4] Write `backend/app/templates/modules/home.html` — description and the readable pages in order. A module with no published pages shows an **empty module, not an error** (spec Edge Cases)
- [ ] T049 [P] [US4] Write `backend/app/templates/modules/page.html` — render the stored body with `|safe` **and no sanitising filter**, because the column is already clean and adding one here would suggest otherwise (research R2)
- [ ] T050 [US4] Include `components/module_nav.html` in every module-scoped template so navigation is a drawer at 360px and a persistent column at desktop widths (FR-033, research R9)

**Checkpoint**: The phase delivers its point — a person reads training assigned to them.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T051 [P] Walk the module list, module home, a content page, the editor, and the roster at **360px, 768px, and 1280px**. The editor's toolbar at 360px is the thing most likely to force sideways scrolling (FR-034, SC-009, done-gate 3)
- [ ] T052 Run done-gate 4 as a check: no module under `backend/app/routers/` imports `Session` or `select`
- [ ] T053 Run done-gate 5 as a check: no endpoint or template receives a `table=True` model instance — four models now, not two
- [ ] T054 Run done-gate 6 as a check: **every** module-scoped service function resolves its module through `module_service.get_for`, with none querying by id directly
- [ ] T055 Confirm `docker compose exec backend pytest` passes against the MySQL container (done-gate 2)
- [ ] T056 Walk all six scenarios in [quickstart.md](./quickstart.md) end to end and tick its **Done when** list — including reading the stored `page.body` column directly to confirm the `<script>` is absent from it
- [ ] T057 Document the permanent-removal procedure in `README.md` — permanently removing a module is a database operation, not an application route (FR-010), and whoever performs it MUST also delete that module's `content_image` rows **and their files from the uploads volume**. Nothing in the application does this, and an orphaned image is never collected (FR-022, research → Accepted simplifications)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: needs Phase 0 working
- **Foundational (Phase 2)**: needs Setup — **blocks every user story**. T013 is the hinge: everything else calls it
- **US1 (Phase 3)**: needs Foundational. Delivers the MVP
- **US2 (Phase 4)**: needs US1 — there is nothing to write pages into until a module exists
- **US3 (Phase 5)**: needs US1. Independent of US2 — people can be registered on a module with no pages
- **US4 (Phase 6)**: needs US2 **and** US3 — a trainee must be registered on something that has readable pages. It is the last story for that reason, not because it matters least
- **Polish (Phase 7)**: needs every story you intend to ship

### Within Each Story

Tests first, and they must fail. Then models, then services, then routers, then templates.

### Parallel Opportunities

- T002, T003, T004 — three different files, all independent
- T007, T008, T009, T010, T011, T012, T014, T015, T016 — the whole foundational layer except `module_service.get_for` itself
- T018, T019 — both US1 test modules
- T026, T027, T028, T029 — all four US2 test modules
- T023 and T024; T034 and T035; T048 and T049 — template pairs

---

## Parallel Example: User Story 2

```bash
# The four test modules first — all must fail before anything below is written:
Task: "tests/services/test_content.py — draft-last, reorder, per-page publish, 5000 words"
Task: "tests/services/test_content_sanitising.py — assert on the stored column, not the render"
Task: "tests/routers/test_content_access.py — 403 for another module's instructor, 404 for a draft"
Task: "tests/services/test_upload.py — extension, size, generated name, renamed .exe accepted"

# Then the two templates, once the service exists:
Task: "backend/app/templates/modules/page_form.html — Quill from the vendored asset"
Task: "backend/app/templates/modules/page_list.html — drafts included, in order"
```

---

## Implementation Strategy

### MVP First

1. Phase 1 → Phase 2 → Phase 3 (US1)
2. **Stop and validate**: quickstart Scenario 1, including the 404-not-403 check
3. An administrator can set modules up and hand them to instructors. Empty, but real

### Incremental Delivery

US1 → US2 → US3 → US4, validating the matching quickstart scenario after each. Every step leaves the platform working, which is Constitution V.

### The two tasks that carry this phase's risk

- **T011 with T012 and T027** — sanitising before storage. Content written once is read by every trainee on the module, and a failure here is silent. The test that matters asserts on the stored column, not on what a template renders
- **T032 with T029** — the generated stored filename. Deriving a path from an uploaded name is the difference between a file store and a way to write anywhere on the volume

### Notes

- Four new tables need only `docker compose up -d --build`. Dropping the volume is for changed columns, not new tables, and this phase changes no column
- Uploads are checked by extension only, images are never scanned, orphaned images are never collected, and concurrent edits lose the earlier one. All four are recorded decisions in research.md, not gaps
- Commit after each task or logical group
