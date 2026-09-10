# Tasks: Platform Foundation — Identity, Access & Shell

**Input**: Design documents from `/specs/001-platform-foundation/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/routes.md](./contracts/routes.md), [quickstart.md](./quickstart.md)

**Tests**: Included. Not optional here — Constitution VI requires tests alongside each feature, FR-036 requires them runnable on demand, and SC-013 requires every user-facing behaviour covered.

**Organization**: Tasks are grouped by user story. Each story phase ends at a checkpoint where that story can be demonstrated.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel — different files, no dependency on an unfinished task
- **[Story]**: US1–US6, matching the user stories in spec.md
- Every task names the exact file it touches

## Path Conventions

Paths are as fixed in [plan.md](./plan.md) → Project Structure, which follows `lms-project-spec.md` §6.2: `backend/app/` for the application, `tests/` at the repository root, `nginx/` for the proxy.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: A repository that builds and starts. Nothing in it works yet.

- [ ] T001 Create the directory skeleton from plan.md: `backend/app/{models,schemas,services,routers,templates,static}`, `backend/app/templates/{auth,admin,emails,components}`, `backend/app/static/{css,js}`, `nginx/`, `tests/{services,routers}`
- [ ] T002 [P] Write `backend/requirements.txt` pinning exact versions of: fastapi, uvicorn[standard], jinja2, sqlmodel, pymysql, argon2-cffi, pydantic-settings, itsdangerous, anyio, python-multipart, pytest, httpx
- [ ] T003 [P] Write `backend/Dockerfile` — `python:3.12-slim`, install `requirements.txt`, run uvicorn on `0.0.0.0:8000`, publish no port itself
- [ ] T004 [P] Write `nginx/Dockerfile` and `nginx/nginx.conf` — serve `/static/` directly from the shared read-only volume, reverse-proxy everything else to `backend:8000`, forward `X-Forwarded-Proto` (research R10, FR-031)
- [ ] T005 Write `docker-compose.yml` — three services (`nginx`, `backend`, `db`); **only `nginx` publishes a port** (80); `db` healthcheck `mysqladmin ping` at a 5-second interval with 10 retries and `backend` on `depends_on: condition: service_healthy`; a named volume for MySQL data (**never a bind mount into the synced project directory**); `--character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci` on the `db` command, so the server matches the connection URL and T012's assert passes; `backend/app/static` mounted read-only into `nginx` (research R5 and R10, FR-031, FR-034)
- [ ] T006 [P] Write `.env.example` with `MYSQL_*`, `SESSION_SECRET`, `SMTP_USER`, `SMTP_APP_PASSWORD`, `SMTP_FROM`, `CODE_TTL_MINUTES=10`, `SESSION_HOURS=12`, `LOGIN_RATE_LIMIT=5`, `LOGIN_RATE_WINDOW_MINUTES=5` — placeholder values only; `.env` itself stays git-ignored (FR-033)
- [ ] T007 [P] Write `backend/app/config.py` — a pydantic-settings `Settings` class reading exactly the keys in `.env.example`, with no default that embeds a credential (FR-033)
- [ ] T008 [P] Vendor Bootstrap 5 and HTMX into `backend/app/static/css/` and `backend/app/static/js/` as committed files — no CDN reference anywhere (research R10)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The two tables, the cross-cutting primitives, the route guards, and a test harness that talks to real MySQL.

**⚠️ CRITICAL**: No user story can begin until this phase is complete.

- [ ] T009 Write `backend/app/database.py` — SQLModel engine over PyMySQL with `charset=utf8mb4`, a `get_session` dependency, and a first-connection retry loop of **10 attempts two seconds apart** (research R5)
- [ ] T010 [P] Write `backend/app/models/user.py` — `table=True` model with exactly: `id` INT PK auto; `email` VARCHAR(255) **unique index**, not null, **stored lowercased**; `full_name` VARCHAR(255) not null; `password_hash` VARCHAR(255) not null; `role` VARCHAR(20) not null, one of `administrator` · `instructor` · `trainee`; `is_active` BOOL not null **default true**; `must_set_password` BOOL not null **default false**; `login_code_hash` VARCHAR(255) **nullable**; `login_code_expires_at` DATETIME **nullable**; `created_at` DATETIME not null, **naive UTC** (data-model.md → `user`)
- [ ] T011 [P] Write `backend/app/models/session.py` — `table=True` model with: `id` VARCHAR(64) PK holding `secrets.token_urlsafe(32)` **stored as issued**; `user_id` INT FK → `user.id`, **indexed**, not null, foreign key enforced by InnoDB; `created_at` DATETIME not null; `expires_at` DATETIME not null, set to `created_at` + 12 hours; `ip` VARCHAR(45) nullable; `user_agent` VARCHAR(255) nullable and truncated to fit (data-model.md → `session`)
- [ ] T012 Write `backend/app/main.py` — the app factory and a lifespan that runs `SHOW VARIABLES LIKE 'character_set_%'` and **raises unless the connection is `utf8mb4`**, then calls `SQLModel.metadata.create_all()`. No migration tool (research R6, Constitution IV)
- [ ] T013 [P] Write `backend/app/security.py` — one Argon2 hasher used for both passwords and codes; `generate_code()` returning `secrets.randbelow(1_000_000)` zero-padded to six digits; `new_session_id()`; a double-submit CSRF dependency (token set as a cookie on any GET rendering a form, matched against a hidden field on POST); and an in-process fixed-window rate limiter in a module-level dict, **five attempts per IP per five minutes**, with periodic pruning (research R2, R3, R9)
- [ ] T014 [P] Write `backend/app/schemas/user.py` — **read models**: a non-table `UserRead` (id, email, full_name, role, is_active, must_set_password) so that no `table=True` instance ever reaches a template or a response (done-gate 5). **Input models**: `UserCreate`, `UserUpdate`, and `PasswordSet`, through which every form post is validated before it reaches a service — the constitution requires input validated through non-table models, because SQLModel does not validate table classes
- [ ] T015 Write `backend/app/dependencies.py` — `current_account` (look the session row up, refuse and delete it if past `expires_at`, refuse if the account is inactive), `require_role`, and `require_password_set` which redirects to `/password/new` while the flag is raised. These touch `Request`, which is why they are here and not under `services/` (research R4, Principle II)
- [ ] T016 [P] Write `backend/app/templates/base.html` and `backend/app/templates/components/nav.html` — responsive Bootstrap shell, English left-to-right, one stylesheet, no direction handling, no CDN link (FR-028, spec Assumptions)
- [ ] T017 [P] Write `tests/conftest.py` — a session-scoped fixture starting a **MySQL 8 container**, creating the schema with `create_all()`, dropping it afterwards, and running each test inside a transaction that is rolled back. SQLite is forbidden (research R7, Constitution VI). Write `pytest.ini` at the repository root with `testpaths = tests`, so pytest never tries to import application modules whose names begin with `test_` — Phase 2 adds `app/models/test.py` and `app/services/test_service.py`, which would otherwise be collected as test modules and fail
- [ ] T018 [P] Write `tests/test_schema.py` — assert the connection character set is `utf8mb4`, that `user.email` carries a unique index, and that `session.user_id` carries an enforced foreign key

**Checkpoint**: `docker compose up` starts all three tiers and creates both tables. Nothing is reachable yet.

---

## Phase 3: User Story 1 — Sign in with a second factor (Priority: P1) 🎯 MVP

**Goal**: Email and password, then a six-digit code by email, then a dashboard. Plus the forced first password change on any account an administrator set up.

**Independent Test**: With a seeded account and a mailbox — sign in, receive a code, enter it, land on a dashboard. Then confirm a wrong code, an expired code, a reused code, and a superseded code are each refused.

### Tests for User Story 1

- [ ] T019 [P] [US1] Write `tests/services/test_auth_service.py` — a table of cases: wrong password refused; inactive account refused; correct password writes `login_code_hash` and `login_code_expires_at` together; correct code clears both and returns a session; **wrong** code refused; code past `login_code_expires_at` refused as expired; an already-used code refused; a code replaced by a fresh sign-in refused (FR-013, FR-016, FR-017, FR-018)
- [ ] T020 [P] [US1] Write `tests/services/test_password_rules.py` — a password shorter than **eight characters** is refused at every place one is set: seeding, administrator creation, administrator reset, and the person's own choice (FR-005, FR-012)
- [ ] T021 [P] [US1] Write `tests/routers/test_login_flow.py` with the mail sender stubbed — the full two-step flow; and that an account with `must_set_password` raised is redirected to `/password/new` from every other route until it sets one (FR-011, SC-012)
- [ ] T022 [P] [US1] Write `tests/routers/test_no_2fa_bypass.py` — a correct password alone reaches no authenticated page: every sign-in requires the emailed code, with **no trusted device, no remembered browser, and no per-account exemption**. The seeded demonstration accounts are exempt from the first-sign-in password change but **not** from the code (FR-014)

### Implementation for User Story 1

- [ ] T023 [P] [US1] Write `backend/app/services/email_service.py` — `smtplib` over `smtp.gmail.com:587` with STARTTLS, executed through `anyio.to_thread.run_sync` under a **ten-second timeout**, awaited inline; raises `EmailDeliveryFailed`. No `Request` or `HTTPException` in this module (research R8, Principle II)
- [ ] T024 [P] [US1] Write `backend/app/templates/emails/login_code.txt` — the code, how long it lasts, and that signing in again issues a new one
- [ ] T025 [US1] Write `backend/app/services/auth_service.py` — `start_login(email, password)` verifying the account is active, generating and hashing the code, writing both `login_code_*` columns and emailing it; `verify_code(email, code)` clearing both columns and creating a session row; `set_own_password(user, password)` enforcing the eight-character minimum and clearing `must_set_password`. Raises `InvalidCredentials`, `InactiveAccount`, `CodeInvalid`, `CodeExpired`, `EmailDeliveryFailed` — never an HTTP exception (Principle II)
- [ ] T026 [US1] Write `backend/app/routers/auth.py` — `GET /login`, `POST /login`, `GET /login/verify`, `POST /login/verify` exactly as contracts/routes.md specifies, each parsing the request and calling one service function. This module must not import `Session` or `select` (done-gate 4)
- [ ] T027 [US1] Apply the rate limiter from T013 to `POST /login` and `POST /login/verify` — five per IP per five minutes (FR-019, research R2)
- [ ] T028 [US1] Apply the CSRF dependency from T013 to every POST in `backend/app/routers/auth.py`, with the token set on each GET that renders a form. **Every router added later in this phase applies it too** — T031 and T039 add routes to files this task has already passed over, and T050 covers administration (FR-025, research R3)
- [ ] T029 [P] [US1] Write `backend/app/templates/auth/login.html` — email and password, keyboard-operable, error message region (FR-029)
- [ ] T030 [P] [US1] Write `backend/app/templates/auth/verify.html` — the code field carrying `autocomplete="one-time-code"` and `inputmode="numeric"` so a phone offers the received code, plus `email` in a hidden field (research R1, FR-029)
- [ ] T031 [US1] Write `backend/app/routers/password.py` and `backend/app/templates/auth/set_password.html` — `GET /password/new` and `POST /password/new`, the only authenticated routes not behind `require_password_set`, with the **CSRF dependency applied to its POST** (contracts/routes.md, FR-011, FR-025)
- [ ] T032 [US1] Write `backend/app/routers/dashboard.py` with `GET /` behind `current_account` + `require_password_set`, rendering a minimal placeholder so sign-in lands somewhere. User Story 2 shapes it by role

**Checkpoint**: A seeded person signs in with a code and reaches a page. This is the MVP — the phase delivers value here.

---

## Phase 4: User Story 2 — See a workspace that matches your role (Priority: P2)

**Goal**: Three roles, three materially different navigations, with refusal at the point of request rather than a hidden button.

**Independent Test**: Sign in as each seeded role in turn; confirm each sees its own navigation and that a trainee requesting `/admin/accounts` receives **403**, not a page with the controls removed.

### Tests for User Story 2

- [ ] T033 [P] [US2] Write `tests/routers/test_role_access.py` — a trainee and an instructor each receive 403 from every `/admin/*` route; an administrator receives 200 (FR-027, quickstart Scenario 2)

### Implementation for User Story 2

- [ ] T034 [US2] Extend `backend/app/templates/components/nav.html` — administrative navigation rendered only for `administrator`, and absent rather than disabled for the other two (FR-026, spec Assumptions)
- [ ] T035 [US2] Write `backend/app/templates/dashboard.html` — three role-shaped panels, largely empty in this phase, with a note that modules arrive in Phase 1
- [ ] T036 [US2] Extend `backend/app/routers/dashboard.py` to pass a `UserRead` (never the `table=True` model) and the role-appropriate view data (done-gate 5)
- [ ] T037 [US2] Apply `require_role("administrator")` from `backend/app/dependencies.py` to the administration router prefix so refusal happens before any handler runs (FR-009, FR-027)

**Checkpoint**: Each role sees its own workspace and cannot reach another's by typing the address.

---

## Phase 5: User Story 3 — End access, immediately (Priority: P2)

**Goal**: Sign-out ends a session, and a deactivated account is refused on its very next request.

**Independent Test**: Sign in and sign out — protected pages unreachable. Separately, deactivate an account while it is signed in and confirm the next request is refused.

### Tests for User Story 3

- [ ] T038 [P] [US3] Write `tests/routers/test_session_lifecycle.py` — after sign-out the session row is gone and the cookie no longer grants access; a session past `expires_at` is refused **and deleted**; deactivating an account refuses its **existing** session on the next request (FR-003, FR-022, FR-023, FR-024, SC-010)

### Implementation for User Story 3

- [ ] T039 [US3] Add `POST /logout` to `backend/app/routers/auth.py` — delete the session row, clear the cookie, redirect to `/login`. Apply the **CSRF dependency** to it: this route is added after T028 already swept that file (FR-023, FR-025)
- [ ] T040 [US3] Set the session cookie in `backend/app/routers/auth.py` with `HttpOnly`, `SameSite=Lax`, and `Secure` derived from the `X-Forwarded-Proto` header Nginx sends (contracts/routes.md → Cookies)
- [ ] T041 [US3] Add an opportunistic sweep of expired session rows for all accounts on each successful sign-in, in `backend/app/services/auth_service.py`. There is no scheduled cleanup in this phase (data-model.md → `session` rules)
- [ ] T042 [US3] Confirm `current_account` in `backend/app/dependencies.py` re-checks `is_active` on **every** request, not only at sign-in (FR-003, SC-010)

**Checkpoint**: Access can be withdrawn at any moment, which is the reason sessions live on the server.

---

## Phase 6: User Story 4 — Administer accounts (Priority: P2)

**Goal**: The only route by which an account comes into existence, changes role, gets a new password, or is switched off.

**Independent Test**: As an administrator — create an account, sign in as it, edit it, change its role to instructor, reset its password, deactivate it, confirming the effect after each step.

### Tests for User Story 4

- [ ] T043 [P] [US4] Write `tests/services/test_admin_service.py` — **every** function refuses a non-administrator caller (done-gate 6); a duplicate email is refused on both create and edit; create and reset each raise `must_set_password`; deactivation and reactivation both work (FR-007, FR-008, FR-009, FR-010)
- [ ] T044 [P] [US4] Write `tests/routers/test_no_self_registration.py` — no route anywhere accepts an account creation from a signed-out visitor, and no template links to one (FR-006, SC-011)

### Implementation for User Story 4

- [ ] T045 [US4] Write `backend/app/services/admin_service.py` — `list_accounts`, `create_account`, `update_account`, `reset_password`, `set_active`. Each takes the acting account and **verifies its role itself** (Principle III, done-gate 6). Email comparison is lowercase, so `Ahmad@x.com` and `ahmad@x.com` are one account (data-model.md)
- [ ] T046 [US4] Enforce in `backend/app/services/admin_service.py` that `create_account` and `reset_password` both set `must_set_password` **true**, and that a password below eight characters is refused (FR-005, FR-010)
- [ ] T047 [US4] Write `backend/app/routers/admin.py` — the seven routes in contracts/routes.md, all behind `admin`, returning `UserRead` objects only. No `Session` or `select` import (done-gate 4, done-gate 5)
- [ ] T048 [P] [US4] Write `backend/app/templates/admin/list.html` — every account with email, name, role, and active state, readable at 360px without sideways scrolling (FR-007, FR-028)
- [ ] T049 [P] [US4] Write `backend/app/templates/admin/form.html` — create and edit, with role selection and the password rule stated on screen (FR-005)
- [ ] T050 [US4] Apply the CSRF dependency to every POST in `backend/app/routers/admin.py` (FR-025)

**Checkpoint**: The platform can take on real people. There is still no delete route — accounts are deactivated, never removed.

---

## Phase 7: User Story 5 — Bring the platform up from nothing (Priority: P3)

**Goal**: One documented command on a clean machine produces a working sign-in page and demonstration accounts.

**Independent Test**: On a machine that has never run this, follow the documented setup and reach a sign-in page with usable accounts inside ten minutes.

### Tests for User Story 5

- [ ] T051 [P] [US5] Write `tests/test_seed.py` — seeding creates **one administrator, one instructor, and five trainees**, all with `must_set_password` **false**, and running it twice creates no duplicates (FR-004, data-model.md → Seed data)

### Implementation for User Story 5

- [ ] T052 [US5] Write `backend/seed.py` — the seven accounts, each with a password meeting the eight-character minimum, printing the addresses and passwords it created. Demonstration accounts are **exempt** from the first-sign-in password change; accounts an administrator creates never are (spec Assumptions)
- [ ] T053 [US5] Write the setup section of `README.md` — `cp .env.example .env`, edit it, `docker compose up -d`, `docker compose exec backend python seed.py`, and the note that changing a model means `docker compose down -v && docker compose up -d` because there are no migrations (FR-030, quickstart)
- [ ] T054 [US5] Verify the boundaries from a shell: `curl http://localhost:3306` and `curl http://localhost:8000` are both refused, and `http://localhost` serves the sign-in page (FR-031, SC-007)
- [ ] T055 [US5] Verify `docker compose restart` leaves every account in place, confirming the MySQL named volume is doing its job (FR-034)

**Checkpoint**: The phase is demonstrable on someone else's machine.

---

## Phase 8: User Story 6 — Be told clearly when email fails (Priority: P4)

**Goal**: A mail outage produces a plain message in seconds, not a wait for a code that will never arrive.

**Independent Test**: Put a wrong `SMTP_APP_PASSWORD` in `.env`, restart the backend, attempt to sign in, and expect a clear message within about fifteen seconds.

### Tests for User Story 6

- [ ] T056 [P] [US6] Write `tests/routers/test_email_failure.py` — with the sender raising, `POST /login` returns the sign-in form carrying a message that the code could not be sent and that signing in again is how to retry; the person is **not** sent to the code-entry page; and the whole attempt returns inside the bounded time (FR-020, FR-021, SC-008)

### Implementation for User Story 6

- [ ] T057 [US6] Handle `EmailDeliveryFailed` in `backend/app/routers/auth.py` — re-render `auth/login.html` with the message, rather than redirecting to `/login/verify` (FR-020)
- [ ] T058 [US6] Confirm the ten-second timeout in `backend/app/services/email_service.py` bounds the failure so the response arrives well inside fifteen seconds (FR-021, SC-008)

**Checkpoint**: A mail outage is legible. There is no way in while mail is down, which quickstart Scenario 6 states plainly.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T059 [P] Walk sign-in, code entry, choose-a-password, dashboard, and account administration at **360px, 768px, and 1280px** — usable at each, navigation as a drawer at 360px, no sideways page scrolling anywhere (FR-028, SC-003, done-gate 3)
- [ ] T060 [P] Confirm every one of those screens is operable by keyboard alone, and that the code field offers a received code on a phone (FR-029)
- [ ] T061 Run done-gate 4 as a check: no module under `backend/app/routers/` imports `Session` or `select`
- [ ] T062 Run done-gate 5 as a check: no endpoint or template receives a `table=True` model instance
- [ ] T063 Confirm `docker compose exec backend pytest` is the single documented command for the whole suite, and that it passes against the MySQL container (FR-036, done-gate 2)
- [ ] T064 Walk all seven scenarios in [quickstart.md](./quickstart.md) end to end and tick its **Done when** list

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: needs Setup — **blocks every user story**
- **US1 (Phase 3)**: needs Foundational. Delivers the MVP
- **US2, US3, US4 (Phases 4–6)**: need Foundational, and in practice need US1, because each is reached only by signing in. Each remains independently *testable* through the session fixture in `tests/conftest.py`
- **US5 (Phase 7)**: needs Foundational. Its seeding is what makes US1–US4 demonstrable, so in practice bring T052 forward if you want accounts to test with
- **US6 (Phase 8)**: needs US1, since it is the failure path of the mail send US1 introduces
- **Polish (Phase 9)**: needs every story you intend to ship

### Within Each Story

Tests are written first and must fail. Then models, then services, then routers, then templates.

### Parallel Opportunities

- T002, T003, T004, T006, T007, T008 — six different files, all after T001
- T010, T011, T013, T014, T016, T017, T018 — the whole foundational layer except `database.py`, `main.py`, and `dependencies.py`
- T019, T020, T021, T022 — all four US1 test modules
- T029, T030 — the two auth templates
- T048, T049 — the two admin templates

---

## Parallel Example: User Story 1

```bash
# The four test modules first — they must fail before anything below is written:
Task: "tests/services/test_auth_service.py — the eight code and credential cases"
Task: "tests/services/test_password_rules.py — the eight-character minimum in four places"
Task: "tests/routers/test_login_flow.py — the two-step flow with mail stubbed"
Task: "tests/routers/test_no_2fa_bypass.py — a password alone reaches nothing"

# Then the two independent pieces of the send path:
Task: "backend/app/services/email_service.py — threadpool SMTP under a ten-second timeout"
Task: "backend/app/templates/emails/login_code.txt — the code email"
```

---

## Implementation Strategy

### MVP First

1. Phase 1 → Phase 2 → **T052 out of order**, so there are accounts to sign in as
2. Phase 3 (US1)
3. **Stop and validate**: quickstart Scenario 1, including all four failure rows
4. That is a demonstrable platform: a real person signs in with a real code

### Incremental Delivery

US1 → US2 → US3 → US4 → US5 → US6, validating the matching quickstart scenario after each. Every step leaves the platform working, which is Constitution V.

### Notes

- There are **no migrations**. Any change to `backend/app/models/` means `docker compose down -v && docker compose up -d` and seeding again — free while no real data exists
- Nothing is backed up, nothing is logged, and there is no audit trail. All three are recorded decisions, not gaps
- Commit after each task or logical group
