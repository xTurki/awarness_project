# SME Cybersecurity Awareness Training Platform — Project Specification

**Status:** Draft v14
**Stack:** Docker · Nginx · Python / FastAPI / Jinja2 / HTMX / Bootstrap 5 · SQLModel · MySQL 8 · Gmail SMTP
**Method:** Spec-driven development, phased delivery

> **Changes from v13:** Phase 4 settled. The retake clock now runs from a person's **most recent** attempt and only if it passed — resolving a conflict with Phases 2 and 3, which already decided the most recent attempt represents a person. A one-off test may carry `completion_deadline_days`, so mandatory training assigned once is chased too. Publishing a replacement test notifies everyone it made due, with no grace period.
>
> **Changes from v12:** Phase 3 gains an instructor view of one module — who is registered, their state, and a way into their attempts. Its state vocabulary is fixed at five (no test available · not started · in progress · passed · failed); *due* and *overdue* need a retake interval and belong to Phase 4. State follows the module's currently published test, so replacing a test resets everyone on that module. No organisation-wide view exists for an administrator. Settled while specifying Phase 3.
>
> **Changes from v11:** Module self-registration removed entirely — `Module.self_registration_open` is gone, and people are always put on a module by an administrator or its instructor. The unused `Module.code` field is dropped. Module creation stays with administrators. This closes the contradiction where a trainee could register themselves on a module they had no way to discover.
>
> **Changes from v10:** **Security surface reduced at the owner's request.** Removed: the break-glass CLI, the signed pending-login cookie (the verify form carries the email instead), identical failure messages for unknown/wrong/disabled login, the `is_active` re-check at the code step, rate limiting on code verification, the ban on codes reaching logs, upload content-sniffing with generated filenames and `nosniff`, the requirement that a new password differ from the administrator's, and the last-administrator guard. Password minimum drops from ten characters to eight. Kept: password hashing, server-side sessions, authorisation in the service layer, HTML sanitising before storage, CSRF, secrets from the environment, and rate limiting on login.
>
> **Changes from v9:** The `archived` module state is removed — modules never end; retiring one means unpublishing it, and renewal comes from the retake interval in §6.5. Registrations lose their `state` column entirely: a registration exists or the person is not on the module, since nothing could produce "invited" or "concluded". Both settled while specifying Phase 1.
>
> **Changes from v8:** Phase 0 synchronised with `specs/001-platform-foundation/spec.md`. Adds administrator account management, the forced password change at first sign-in (`User.must_set_password`, §6.4), the guard against removing the last active administrator, an explicit non-goal for account self-registration, and a ten-character minimum password. Automated checks on every change are deferred; version control is established in Phase 0.
>
> **Changes from v7:** **Module content added** (§6.6) — instructors author ordered pages inside the platform, Canvas-style, with a vendored rich-text editor, server-side HTML sanitising, and image upload. New `Page` and `ContentImage` tables, a second named volume, and Nginx serving uploads. Content and test are never gated against each other. Multiple-choice questions may have several correct answers, scored all-or-nothing. This reverses v7's "no content feature" and reopens file storage, narrowly — instructors upload images; trainees still upload nothing.
>
> **Changes from v6:** Attempt limits no longer apply to recurring tests — unlimited retakes until a trainee passes, removing the stuck state where someone could be permanently overdue with no way out. No content-serving feature: the four training modules are ordinary module records created by hand. Quizzes keep specific chosen questions rather than a random draw. No instructor progress view. §12 is now a record of where this specification deliberately diverges from the project proposal, which is a starting document and not a contract.
>
> **Changes from v5:** Reframed from a school LMS to an **SME cybersecurity awareness platform**, matching the project proposal. Terms removed entirely — modules start and end whenever their instructor decides. Entities and roles renamed throughout: `Course`→`Module`, `Enrollment`→`Registration`, teacher→instructor, student→trainee, admin→administrator, and the unused `ta` role dropped. The Phase 3 gradebook is replaced by a trainee results view; `GradeColumn` and `GradeEntry` are gone, along with weighting, manual grade entry, and final marks.
>
> **Changes from v4:** Assessment narrowed to **multiple choice only** — true/false and short answer removed, so the `Question.type` column is gone. Assignments, submissions, and file upload dropped entirely rather than deferred; the phase plan is now Phases 0–4. Every question is machine-scored, which means no attempt ever waits on a human marker. Both changes align the spec with the proposal's stated assessment model.
>
> **Changes from v3:** Recurring test schedules, notifications, and self-registration added to close the gaps in the requirements list (§6.5, new Phase 4). "Module owner" confirmed to mean the instructor registered on the module — no new entity. Pathways considered and dropped.
>
> **Changes from v2:** Two-factor authentication added — a six-digit code emailed via Gmail/Workspace SMTP, required of every role on every login (§6.4). The pending code lives in two nullable columns on `User`; there is no challenge table, no resend route, and no attempt counter. Audit logging removed from the system entirely. Lands in Phase 0 alongside session auth, and adds the project's only outbound network dependency.
>
> **Changes from v1:** PostgreSQL → MySQL 8. SQLAlchemy 2.0 → SQLModel. Alembic migrations removed (greenfield, no data to preserve). Deployment is now a three-tier Docker Compose stack. Repository layer collapsed into services. Responsive target raised from "tablet width" to phone-first. Rationale for each is recorded inline.

---

## 1. Project Constitution

These are the standing principles. Every phase spec is written under them, and no phase gets to violate one for convenience.

1. **Routers never touch the database.** HTTP handling and business logic stay separate. A router parses the request, calls a service, and renders a template. Nothing more.
2. **Services never touch HTTP objects.** No `Request`, no `Response`, no cookies inside the service layer. Services take plain arguments and return plain data. This is what makes them testable and reusable.
3. **Authorisation is enforced in the service layer.** Hiding a button in the template is not security. Every service method that acts on a module verifies the caller's relationship to that module.
4. **The schema is generated from the models.** `SQLModel.metadata.create_all()` at startup is the only schema authority. There are no migrations and no migration tool. Changing a model before launch means dropping and recreating the database — which is free, because there is no production data. See §5.3 for the exact point at which this principle expires.
5. **Every phase ends with working, deployed software.** No phase is "the database phase" or "the auth phase" with nothing to show. Each one delivers something a real user can log in and do. "Deployed" means `docker compose up` brings the whole stack to a working state.
6. **Tests accompany the feature, not follow it.** Service-layer tests are non-negotiable. Router tests where behaviour is non-obvious.
7. **Non-goals are defended.** Adding a feature outside the current phase requires deleting something else or moving it to a later phase explicitly.
8. **Simplicity is a requirement, not a preference.** Every added layer, service, container, or dependency must justify itself against a concrete problem that exists *now*. Complexity is the primary source of defects in a project this size.

---

## 2. Goals

### Primary goal

A self-hosted **cybersecurity awareness training platform for a single small or medium-sized enterprise** — an organisation with little or no dedicated IT staff, whose people are expected to recognise threats without specialist training. It is a low-cost, self-hosted alternative to per-seat commercial awareness subscriptions.

- an **administrator** manages user accounts, modules, and registrations
- an **instructor** owns modules, maintains their question banks, builds and schedules tests, decides how often each must be retaken, and registers trainees onto them
- a **trainee** registers for modules, takes tests, sees where they stand, and is told when something is due

"Module owner" in the requirements means the instructor registered on that module. They are the same person.

### There are no terms

Modules do not belong to a semester, a cohort, or an academic calendar. A module is either published or it is not, and it starts and ends whenever its instructor decides. Nothing carries a term, an intake date, or an end-of-period rollover.

This follows from the audience. An SME onboards one person in March and another in November; training is continuous, not timetabled. Every decision that would have been justified by "at the end of term" is therefore justified another way or removed — the weighted gradebook was the largest of them, and it is gone.

### Success criteria

The project succeeds when an instructor can run a module end to end without a developer intervening, in both of these shapes:

1. **One-off training** — publish a module, register trainees or let them register themselves, deliver a test, and see who has passed.
2. **Recurring training** — set a retake interval and a pass mark once, after which the system tracks who is due, tells them, and keeps doing so every cycle without anyone maintaining a spreadsheet.

The second is the harder criterion and the more valuable one, because it is the part that a spreadsheet plus a reminder in someone's calendar does badly.

### Design priorities (in order)

1. **Clean architecture that can grow** — the layering survives Phase 4 and beyond
2. **Correct by default where it matters** — authorisation in the service layer, a second factor on every login, and server-authoritative timing are properties of the design, not features to be retrofitted
3. **Canvas-like look and feel** — familiar navigation, module cards, left-hand module nav
4. **Works on the device the user actually has** — phone, tablet, or desktop, same web app
5. **Ship working software quickly** — each phase is weeks, not months
6. **Depth in FastAPI** — a welcome by-product, not the driver

---

## 3. Non-Goals

Explicitly out of scope. These exist to be pointed at when scope creep arrives. Grouped so the relevant few can be found during a phase rather than the whole list re-read.

**Architecture and deployment**

| Not building | Why |
|---|---|
| Multi-tenancy | One organisation, one database, one domain. Multi-tenancy is an architectural tax paid forever. |
| A separate JavaScript frontend (React/Vue SPA) | A second codebase, a build toolchain, a hand-maintained API contract, and CORS — for a server-rendered app that needs none of it. Jinja2 + HTMX covers the interactivity required. |
| Kubernetes, service mesh, autoscaling | One organisation. One host. Docker Compose is the correct size. More than one `backend` replica additionally breaks the in-process scheduler (§6.5). |
| Native mobile apps | Responsive web only — see §10 Presentation. |
| A job queue or worker container | The scheduler runs in-process. See the non-choice note in §4. |

**Teaching and assessment**

| Not building | Why |
|---|---|
| Module pathways, curriculum tracks, prerequisites | Considered and dropped. Modules are registered onto individually; there is no bundle, sequence, or unlock chain. |
| Assignments, submissions, and trainee file upload | A trainee never uploads anything. Assessment is entirely multiple choice, so there is nothing to submit and nothing to mark by hand. Instructor image upload for content (§6.6) is the only file handling in the system, and it is deliberately narrow. |
| Content prerequisites or completion gating | Content and test are both always available. No "must read this before the test" rules, no per-page view tracking, no unlock chains. |
| Question types other than multiple choice | Multiple choice only. True/false is a two-option multiple choice, and short answer would require a human marker, which would break the automatic pass/fail the recurrence cycle depends on (§6.5). |
| Terms, semesters, cohorts, academic calendars | Training in an SME is continuous, not timetabled. A module is published or it is not. |
| Weighted grades, final marks, manual grade entry | Every question is machine-scored and no period ever concludes, so there is nothing to weight and no final mark to publish. Phase 3 shows results instead. |
| Rubrics engine, outcomes, competency mapping | Canvas'''s most complex subsystem. Automatic scoring covers the need. |
| Plagiarism detection | Requires external services and a corpus. |
| Learning analytics dashboards | Needs data that does not exist yet. |

**Authentication and accounts**

| Not building | Why |
|---|---|
| Self-registration of any kind | Nobody creates their own account, and nobody puts themselves on a module. An administrator creates accounts; an administrator or the module's instructor registers people onto modules. Considered for modules and dropped — mandatory training is assigned, not opted into, and a browse-and-join page was work for a case that does not arise. |
| SMS or authenticator-app second factors | One second-factor channel is enough for one organisation. Each additional channel is a registration flow, a recovery flow, and a support burden. |
| Trusted-device or "remember me" exemption from 2FA | Every login carries the second factor, for every role. Decided knowingly; the availability cost is recorded in §11. |
| Self-service password reset | Tempting now that the system can send mail. It is a second token lifecycle and a second email flow, for an organisation whose administrator is reachable in person. The administrator resets passwords, and the owner then chooses their own at their next sign-in. |
| A resend-code route | Logging in again issues a fresh code and overwrites the old one, so "start over" already is the resend. A dedicated route adds a cooldown, a send counter, and its own tests for no capability that does not already exist. |
| Audit logging | Removed deliberately. One organisation, one administrator, and a database that can be read directly. Recorded here so it does not drift back in; the consequence is noted in §11. |

**Communication**

| Not building | Why |
|---|---|
| Announcements, discussions, user-to-user messaging | Outbound mail carries login codes and the four notification triggers in §6.5, and nothing else. |
| Real-time chat, video, conferencing | Enormous surface area; every organisation already uses Zoom, Meet, or Teams. |
| Per-user notification preferences or unsubscribe | Every user receives all four triggers. Mandatory training that can be silently muted is not mandatory. Revisit only if it becomes a real complaint. |

**Integration**

| Not building | Why |
|---|---|
| LTI, SCORM, third-party tool integration | Specification-heavy standards that would dominate the project. |
| SIS import / sync | Administrator CSV upload at most, much later. |

---

## 4. Technology Decisions

| Layer | Choice | Rationale |
|---|---|---|
| Runtime / packaging | **Docker + Docker Compose** | Three tiers, one command, identical on the developer machine and the organisation's server. |
| Web / static tier | **Nginx** | Serves CSS/JS/fonts directly, reverse-proxies everything else to FastAPI, terminates TLS. Keeps static file serving out of the Python process. |
| Web framework | **FastAPI** | Async, typed, excellent dependency injection for auth and DB sessions. |
| Templating | **Jinja2**, server-rendered | Avoids maintaining a second frontend codebase. |
| Interactivity | **HTMX** | Inline grade editing and quiz navigation feel modern without a SPA framework. |
| CSS | **Bootstrap 5** + a custom theme layer | Fast to build; ships a mobile-first responsive grid for free; the theme layer is where the Canvas-like styling lives. |
| Database | **MySQL 8** | InnoDB gives real foreign keys and transactions; native `JSON` column type covers quiz payloads. |
| ORM | **SQLModel** | One class defines both the table and the Pydantic schema, which removes a whole category of duplicated model code. Sits on SQLAlchemy, so dropping to raw SQLAlchemy for a hard query is always available. |
| Schema management | **`create_all()` at startup** | No Alembic. Greenfield project with no data to preserve. See §5.3. |
| Validation | **Pydantic v2**, via SQLModel | Request/response schemas. See the caveat in §5.2 — table models are not automatically safe response models. |
| Auth | **Session cookies**, sessions stored in MySQL | Deliberately *not* JWT. Deliberately *not* Redis — a `sessions` table avoids a fourth container. |
| Second factor | **Six-digit code emailed on every login** | Every role, every login, no trusted-device exemption. Full flow in §6.4. |
| Mail transport | **Gmail / Workspace SMTP** on `smtp.gmail.com:587` | Authenticated with a Google **App Password** — Google no longer permits SMTP with an account password. Sent inline from `backend`; no fourth container. |
| Content authoring | **Vendored rich-text editor** (Quill or equivalent) | Served from the application's own static files, not a CDN. Produces HTML, which is sanitised server-side against an allowlist before storage — the editor is convenience, never a security boundary (§6.6). |
| Image storage | **Named Docker volume**, metadata in MySQL | Instructor uploads only. The only file handling in the system. |
| Scheduled work | **APScheduler, in-process** | Started from the FastAPI lifespan inside the existing `backend` container. Required because due and overdue notices must fire with nobody logged in. No broker, no worker container, no cron container. Assumes a single `backend` replica — see §11. |
| Notifications | **In-app list plus email** | One `Notification` row per module per event is the record; email is a delivery attempt on top of it, and due/overdue mail is batched into one digest per user per run. Read state and de-duplication live on the row. Full design in §6.5. |
| Password hashing | **Argon2** (or bcrypt) | Never anything else. One-time codes are hashed with the same function. |
| Testing | **pytest** + a throwaway MySQL container | Service layer coverage is the priority. Test against MySQL, not SQLite — see §5.4. Mail is sent through a null sender in tests. |

### Deliberate non-choice: JWT

Worth calling out because nearly every FastAPI tutorial reaches for it. JWTs cannot be revoked without server-side state, which defeats their purpose; you need logout, forced password reset, and administrator-disables-account. Server-side sessions give you all three trivially.

### Deliberate non-choice: Redis

Sessions, and later any caching, live in MySQL. Redis is a fourth container, a second persistence story, and a new failure mode, in exchange for performance this application will never need. Revisit only if session reads become a measured bottleneck.

### Deliberate non-choice: a job queue for outbound mail

Sending a login code is the only outbound mail this system produces, and the user is sitting in front of the browser waiting for it — deferring it to a worker gains nothing a user can perceive. Celery or RQ would add a broker, a worker container, and a whole second failure surface to move one `smtplib` call off the request path. The code is sent inline, in a worker thread, under a hard timeout. Revisit only if bulk mail is ever added, which §3 currently forbids.

---

## 5. Data Layer

### 5.1 MySQL specifics that will bite if ignored

These are not general advice; each one is a concrete difference from the PostgreSQL assumptions in v1.

- **Character set must be `utf8mb4`.** Anything else silently mangles emoji and many non-Latin scripts. Set it on the server, the database, and the connection string.
- **Strings need a length.** SQLModel maps a bare `str` to `VARCHAR(255)`. That is fine for names and emails but wrong for a quiz question prompt — declare long text explicitly with a `Text` column type.
- **Indexed string columns are length-limited.** A `utf8mb4` index key is capped; `VARCHAR(255)` is the practical maximum for a unique index such as `user.email`. Do not widen it casually.
- **InnoDB, always.** It is the MySQL 8 default, but it is what makes constitution-level foreign key enforcement real. Never MyISAM.
- **`JSON` is not `JSONB`.** MySQL stores and validates JSON but cannot index inside it the way PostgreSQL can. This is acceptable because quiz payloads are read whole, by primary key, and never searched into. Do not design a feature that queries inside a JSON column.
- **`DATETIME` carries no timezone.** Store UTC, as naive `DATETIME`, everywhere. Convert to the user's timezone in the template layer only. This makes the §11 timezone risk a code-review item on every date field.
- **The driver is `PyMySQL`.** Connection URL: `mysql+pymysql://user:pass@db:3306/lms?charset=utf8mb4`. The host is `db` — the Compose service name — not `localhost`.

### 5.2 SQLModel caveats

- **A table model is not a response model.** `class User(SQLModel, table=True)` contains `password_hash`. Returning it from an endpoint or passing it to a template leaks the hash. Keep separate non-table `UserRead` / `UserCreate` models — the saving from SQLModel is that they are short and share a base, not that they disappear.
- **Validation does not run on table models.** SQLModel skips Pydantic validation for `table=True` classes. Validate at the boundary using the non-table input models; never by trusting the table class.
- **Relationships still need care.** `Relationship()` uses SQLAlchemy lazy loading underneath; N+1 queries are a real risk on any list that shows one row per registration — the results view in Phase 3 most of all. Load explicitly when rendering a list.

### 5.3 When "no migrations" expires

This is the one decision in this spec with an expiry date, so it is written down rather than discovered later.

`create_all()` only ever *creates missing tables*. It does not alter an existing one. Adding a column to a model whose table already exists does nothing — the app then fails at runtime against a stale schema.

**Until first real use:** the workflow is `docker compose down -v` (which drops the volume) then `up`, and the seed script repopulates. Costless, and it should become reflexive.

**The moment a real instructor enters real data, this principle is void.** At that point either adopt Alembic, or accept hand-written `ALTER TABLE` scripts as the schema record. This is expected to land around the end of Phase 3. It is deferred, not avoided.

### 5.4 Testing against MySQL, not SQLite

Tempting shortcut, worth refusing: SQLite does not enforce foreign keys by default, has no real `VARCHAR` length enforcement, treats `JSON` as text, and differs on string comparison and case sensitivity. Every one of those is something this spec relies on MySQL for. Tests run against a disposable MySQL container so that a passing test means something. This is one place where the simpler option is the wrong one.

---

## 6. Architecture

### 6.1 Deployment topology

Three tiers, three containers, one `docker compose up`.

```
                browser (phone / tablet / desktop)
                              |
                              v
+---------------------------------------------------------+
|  nginx          :80 / :443     <- the only exposed port  |
|  - serves /static/* from a shared volume                 |
|  - reverse-proxies everything else to backend:8000       |
|  - TLS termination                                       |
+---------------------------------------------------------+
                              |  internal docker network
                              v
+---------------------------------------------------------+
|  backend        :8000   (not published to the host)      |
|  - uvicorn -> FastAPI -> Jinja2 templates                |
|  - all application logic                                 |
+---------------------------------------------------------+
                              |  internal docker network
                              v
+---------------------------------------------------------+
|  db             :3306   (not published to the host)      |
|  - MySQL 8, InnoDB, utf8mb4                              |
|  - named volume for persistence                          |
+---------------------------------------------------------+
```

**Rules for this topology:**

- **Only Nginx publishes a port.** `backend` and `db` are reachable only on the Compose network. A database port exposed to the host is the most common self-hosting mistake and this design forbids it.
- **`backend` must not query before MySQL is ready.** `depends_on` alone does *not* wait for readiness — it waits for the container to start, and MySQL takes several seconds beyond that on first run while it initialises the data directory. Use a Compose healthcheck (`mysqladmin ping`) with `condition: service_healthy`, and still retry the first connection in application code.
- **Secrets come from the environment.** DB password and session secret via `pydantic-settings`, sourced from a git-ignored `.env`. A committed `.env.example` documents the variable names. No credentials in the compose file or baked into an image.
- **The MySQL data volume is named, not a bind mount.** Bind-mounting a MySQL data directory into an iCloud-synced Windows folder — which is where this project lives — will corrupt it. This is not a hypothetical.
- **Static files are shared, not duplicated.** `backend/app/static/` is mounted into the Nginx container so both tiers see one copy.
- **Uploaded images live in a second named volume**, mounted into both `backend` (which writes them) and `nginx` (which serves them). `client_max_body_size` must match the application's own upload limit — if they disagree, an oversized upload dies in Nginx with an error the application never sees and cannot explain to the instructor.
- **`backend` requires outbound egress to `smtp.gmail.com:587`.** This is the only outbound network dependency in the entire system, and it sits on the login path. If it is blocked — by an organisation firewall, an outbound-deny rule, or a Google outage — nobody can log in. Verify egress as part of deployment, not on the first day the platform is used.

### 6.2 Application layout

```
.
├── docker-compose.yml
├── .env.example              # committed; .env is not
├── nginx/
│   ├── Dockerfile
│   └── nginx.conf
└── backend/
    ├── Dockerfile
    ├── requirements.txt
    ├── seed.py               # creates the demo administrator / instructor / trainees
    └── app/
        ├── main.py           # app factory, middleware, routers, create_all()
        ├── config.py         # settings via pydantic-settings
        ├── database.py       # engine, session factory, DB dependency, connect retry
        │
        ├── models/           # SQLModel tables — the schema
        │   ├── user.py       # incl. the two login_code_* columns
        │   ├── session.py
        │   ├── module.py
        │   ├── page.py
        │   ├── content_image.py
        │   ├── registration.py
        │   ├── quiz.py
        │   └── notification.py
        │
        ├── schemas/          # non-table SQLModel in/out models
        │
        ├── services/         # business logic + authorisation + queries
        │   ├── auth_service.py
        │   ├── email_service.py
        │   ├── module_service.py
        │   ├── content_service.py
        │   ├── quiz_service.py
        │   ├── results_service.py
        │   └── notification_service.py
        │
        ├── routers/          # HTTP endpoints, thin
        │   ├── auth.py
        │   ├── admin.py
        │   ├── modules.py
        │   ├── content.py
        │   ├── quizzes.py
        │   ├── results.py
        │   └── notifications.py
        │
        ├── templates/        # Jinja2
        │   ├── base.html
        │   ├── auth/
        │   │   ├── login.html
        │   │   └── login_verify.html
        │   ├── emails/
        │   │   └── login_code.txt
        │   ├── components/
        │   └── modules/
        │
        └── static/           # also mounted into the nginx container
            ├── css/
            └── js/

tests/
├── conftest.py
├── services/                 # the bulk of the tests
└── routers/
```

### 6.3 Dependency direction

```
routers -> services -> models
```

Strictly one-way. A service never imports a router.

**The repository layer from v1 is removed.** Under constitution principle 8: with SQLModel, a repository method is typically a one-line `session.exec(select(...))` wrapped in a class, and that indirection buys nothing at this scale.

What this must **not** become: raw `select()` calls drifting into routers. Principle 1 is unchanged and is now the only thing holding that line, so it is enforced strictly — **a router that imports `select` or `Session` is a review failure.** If services later grow unwieldy with query code, reintroducing repositories is a mechanical refactor, not a rewrite.

### 6.4 Authentication flow — password plus emailed code

**email + password → code → access.** Every login, every role.

There is no challenge table. The pending code lives in two nullable columns on the user's own row.

**Step 1 — credentials**

`POST /login` → `auth_service.start_login(email, password)`

- Verify the password, check the account is active.
- On success, write `login_code_hash` and `login_code_expires_at` to the user row, email the six-digit code, and show the verify form. The form carries the email address so step 2 knows which account it is checking.
- No session is created yet.

**Step 2 — the code**

`POST /login/verify` → `auth_service.verify_login(email, code)`

- A code is set for that account and `now <= login_code_expires_at`.
- The submitted code matches `login_code_hash`.
- On success: clear both columns, create the `Session`, set the session cookie.

**No resend route.** If the mail does not arrive, log in again — that issues a fresh code and overwrites the old one.

**Routes**

`GET /login` · `POST /login` · `GET /login/verify` · `POST /login/verify` · `POST /logout`

**Settings**

| Setting | Default |
|---|---|
| `OTP_TTL_MINUTES` | 10 |
| `SMTP_TIMEOUT_SECONDS` | 10 |

**Sending**

`email_service.send(to, subject, body)` wraps `smtplib` over `smtp.gmail.com:587` with STARTTLS, authenticated by a Google App Password. The call blocks, so it runs in a worker thread under `SMTP_TIMEOUT_SECONDS` and is awaited inline — the login POST takes a second or two. A delivery failure is shown on the login form as "we could not send your code, please try again"; retrying means logging in again.

**Code handling**

- Six digits, stored as a hash, cleared on successful use and overwritten by any new login attempt.
- The verify field uses `inputmode="numeric"` and `autocomplete="one-time-code"`, so a phone offers the code straight from the mail notification.

**First sign-in after an administrator sets a password**

There is no way for anyone to create their own account. Every account comes from an administrator or from the seed script, which means every account starts life with a password its owner did not choose and someone else knows.

`User.must_set_password` is raised the moment an administrator creates an account or resets one. Once that account clears both login steps, it reaches a choose-a-password screen and nothing else — every other route redirects back to it until a new password is set. The new password must meet the same standard as any other. Setting it clears the flag.

The person is not asked for the administrator's password again on that screen. They proved possession of it, and of the mailbox, moments earlier; a third demand adds friction without adding proof.

Seeded demonstration accounts are exempt, so the platform can be shown working without a detour.

> Without this, every password an administrator has ever issued or reset stays valid and stays known to them. It is what makes "the administrator resets passwords" (§3) an acceptable substitute for self-service recovery rather than a standing back door.

### 6.5 Recurring tests and notifications

Throughout this section **module** means `Module` and **module owner** means the instructor holding the instructor registration on it. They are the same entities under different names, not new ones.

**Recurrence — set by the module owner**

`Quiz.retake_interval_days`, nullable. Null is the default and means a one-off test, which covers most quizzes. A value means the test must be retaken on that cadence — a cybersecurity awareness module might use 90 or 365.

Due dates are **computed, never stored**:

```
for each (user, quiz):
    if retake_interval_days is set:
        last = that user's most recent submitted attempt
        due_at = last.submitted_at + retake_interval_days   if last passed
                 now                                        otherwise, or if none
    elif completion_deadline_days is set:
        due_at = registration.registered_at + completion_deadline_days
                 (never due again once they pass)
    else:
        no due date, ever
```

**The cycle runs from the most recent attempt, and only if it passed.** Someone who passed and then retook and failed is due immediately — the same rule Phases 2 and 3 use to decide what represents a person, applied to dates. A failed attempt therefore never clears an overdue state. This is what makes the recurrence meaningful for something like cybersecurity awareness, where the point is competence rather than attendance.

> **Validation rule:** `passing_score` is **required whenever `retake_interval_days` is set.** A recurring test with no pass mark has no way of knowing when its cycle restarts. This is checked when the owner saves the quiz, not discovered later by the scheduler.

**Attempt limits do not apply to recurring tests.** When `retake_interval_days` is set, `allowed_attempts` is ignored and a trainee may retake as often as they need until they pass.

This is not a convenience. Because the cycle restarts only on a pass, a trainee who exhausted a fixed attempt limit without passing would be permanently overdue, nagged every week, and unable to do anything about it — a stuck state with no exit that the trainee controls. Removing the limit removes the state. Mandatory training measures competence, not whether someone got it right first time, so there is nothing to protect by capping attempts.

`allowed_attempts` still applies normally to one-off quizzes, where no such cycle exists.

A user who has never passed a recurring test is due the moment they are registered. Because nothing is stored, an owner changing the interval re-dates every registered user at once — which is what "totally customisable" has to mean in practice.

**Triggers**

| Trigger | Fires | Needs the scheduler |
|---|---|---|
| Registered onto a module | When an administrator or instructor registers someone | No |
| Result available | When an attempt reaches `graded` | No |
| Test due soon | `DUE_SOON_LEAD_DAYS` before `due_at` | Yes |
| Test overdue | After `due_at`, repeating every `OVERDUE_REMINDER_INTERVAL_DAYS` until an attempt is submitted | Yes |

**Delivery**

Every event creates one `Notification` row — one per module, always. The in-app list is those rows rendered, so a user with five overdue modules sees five entries and can act on each.

Email is a delivery attempt recorded on those rows via `emailed_at`, and **one email may cover several rows**:

| Trigger | Email |
|---|---|
| Registered onto a module | One email, sent immediately |
| Result available | One email, sent immediately |
| Due soon / overdue | **One digest email per user per run**, listing every module due or overdue for them that day |

The digest exists because these two triggers repeat. Thirty users with five overdue modules each is 30 emails a week rather than 150, which keeps the load well inside Gmail's limits and stops the reminders reading as spam to the person receiving them.

A user therefore never receives an email about anything missing from their in-app list, and the two channels cannot disagree — they simply group differently.

**Idempotency** rests on two things. The unique key `(user_id, kind, subject_type, subject_id, due_date)` prevents duplicate rows. The digest then sends only rows where `emailed_at IS NULL` and stamps every row it included. Re-running the daily job therefore finds nothing unsent and emails nobody.

**The scheduler**

APScheduler, started in the FastAPI lifespan inside the existing `backend` container. One job, once a day: find who is due soon or overdue, insert the missing rows, then send one digest per affected user and stamp the rows it covered.

Its one real constraint is that it **assumes exactly one `backend` replica.** Two replicas means two schedulers. The unique key makes the failure mode wasted work rather than duplicate emails, but scaling the backend requires revisiting this first, not afterwards.

**Settings**

| Setting | Default |
|---|---|
| `DUE_SOON_LEAD_DAYS` | 14 |
| `OVERDUE_REMINDER_INTERVAL_DAYS` | 7 |
| `SCHEDULER_RUN_HOUR_UTC` | 6 |

### 6.6 Module content

An instructor authors a module's material inside the platform, the way Canvas works. Content is not static files and not prepared elsewhere — it is created, edited, and reordered through the application.

**Structure**

A module holds an ordered list of pages. Each page has a title, a body, a position, and its own `draft` / `published` state, so an instructor can work on section four while the first three are live. Trainees see published pages only, in order, with the test linked at the end.

**Authoring**

A vendored rich-text editor — Quill or equivalent, served from the application's own static files rather than a CDN. The instructor gets bold, headings, lists, and links without knowing Markdown.

> **The editor is a convenience, not a security boundary.** What it produces is HTML, and HTML from a browser cannot be trusted no matter which editor generated it. Every submitted body is sanitised **server-side** against a tag and attribute allowlist before it is stored — `<script>`, event handlers, `javascript:` URLs, `<iframe>`, `<style>` all stripped. Sanitising in the editor only, or on render only, is not sufficient: stored HTML is read back by every trainee who opens the page, so an unsanitised body is stored cross-site scripting against the whole organisation.

**Images**

Instructors may upload images into a page. This is the one place file storage exists, and it is narrower than it looks:

- Instructors only. **A trainee never uploads anything** — assignments and submissions remain out of scope (§3).
- Images only, by extension, from a short allowed list.
- A size cap. Nginx `client_max_body_size` and the application limit must agree, or a too-large upload fails with a confusing Nginx error instead of a useful message.
- Stored in a named Docker volume and served by Nginx.
- Deleting a module deletes its images.

**No gating**

Content and test are both available from the module home page. A trainee may take the test without opening a single page. This is deliberate: for an annual refresher, someone who already knows the material should not be made to click through it, and the pass mark is what actually establishes competence. It also means no per-page view tracking and no unlock rules.

---

## 7. Domain Model (initial sketch)

**User** — id, email (unique, ≤255), password_hash, full_name, role (`administrator` | `instructor` | `trainee`), is_active, must_set_password, created_at, login_code_hash (nullable), login_code_expires_at (nullable)
> `must_set_password` is raised whenever an administrator creates the account or resets its password, and cleared when the owner chooses their own (§6.4). The two `login_code_*` columns are the whole of the second-factor state (§6.4). They hold the pending code between step 1 and step 2, are cleared on success, and are overwritten by any new login attempt. Like `password_hash`, they are one more reason a `table=True` User must never be rendered or returned.

**Session** — id (opaque random token, primary key), user_id, created_at, expires_at, ip, user_agent
> New in v2. Server-side sessions live here rather than in Redis. Logout deletes the row; expired rows are swept on login.

**Module** — id, title, description (Text), state (`unpublished` | `published`), created_at
> No `term`, no start date, no end date, and no archived state. A module is available when published and not otherwise. Retiring one means unpublishing it; training is continuous and is renewed by the retake interval in §6.5, not by closing the module off. Timing that actually matters lives on the quiz, as an availability window or a retake interval.

**Page** — id, module_id, position, title, body (MediumText), state (`draft` | `published`), created_at, updated_at
> A module's content, authored in the app (§6.6). `body` holds sanitised HTML and is `MEDIUMTEXT` rather than `TEXT` — 64KB is not much once a page carries formatting markup, and hitting that ceiling would truncate an instructor's work silently.

**ContentImage** — id, module_id, stored_name, original_name, mime_type, size_bytes, uploaded_by, uploaded_at
> One row per uploaded image. The file itself lives in a named volume under `stored_name`, which is generated, never the name the instructor's file arrived with. `original_name` is kept for display only and is never used to build a path.
> "Module" in the requirements is this entity, and "module owner" is the instructor registered on it. There is no code field — the title identifies it — and no self-registration flag, because people are always put on a module by someone else.

**Registration** — id, user_id, module_id, role_in_module (`instructor` | `trainee`), registered_at

> A registration carries no status: it exists, or the person is not on the module. There is nothing to accept and nothing to conclude.
>
> Note: a user's *global* role and their *role in a module* are separate. An instructor may be a trainee in another module. Modelling this correctly now avoids a painful schema rebuild later.

**Quiz** — id, module_id, title, instructions (Text), state, available_from, available_until, time_limit_minutes, allowed_attempts, shuffle_questions, retake_interval_days (nullable), completion_deadline_days (nullable), passing_score (nullable)
> `retake_interval_days` is the module owner's retake frequency (§6.5); null means a one-off test. `passing_score` is the mark at or above which an attempt counts as passed, and is **required whenever `retake_interval_days` is set**, because the recurrence cycle restarts on a pass. When `retake_interval_days` is set, `allowed_attempts` is ignored — retakes are unlimited until the trainee passes (§6.5). `available_from` / `available_until` remain the window a single sitting must fall inside; the interval is the cadence on which sittings recur.

**Question** — id, quiz_id, position, prompt (Text), points
> Multiple choice only. There is no `type` column, because there is only one type. A true/false question is a multiple-choice question with two options, so nothing is lost by not modelling it separately. Every question is machine-scorable, which is what keeps `passing_score` and the recurrence cycle in §6.5 fully automatic — no attempt ever waits on a human to mark it.
>
> **A question may have more than one correct option, and scoring is all-or-nothing.** The trainee's selected set must match the correct set exactly: miss a correct option or add a wrong one and the question scores zero. There is no partial credit, which keeps scoring a single set comparison and keeps the pass mark meaning exactly what it appears to mean. Questions with several correct answers render as checkboxes, those with one as radio buttons — the builder infers which from how many options are flagged correct, so the instructor never picks a mode.

**AnswerOption** — id, question_id, text, is_correct
> Any number of options on a question may be flagged correct. At least one must be, and at least two options must exist — both validated when the instructor saves the question, since neither is recoverable once a trainee is mid-attempt.

**QuizAttempt** — id, quiz_id, trainee_id, attempt_number, started_at, submitted_at, state (`in_progress` | `submitted` | `graded`), score

**AttemptAnswer** — id, attempt_id, question_id, response (JSON), is_correct, points_awarded

**Notification** — id, user_id, kind (`registered` | `result` | `due_soon` | `overdue`), subject_type, subject_id, due_date (nullable), title, body (Text), created_at, read_at (nullable), emailed_at (nullable)
> unique (user_id, kind, subject_type, subject_id, due_date)
>
> The row is the notification. In-app rendering reads it, email delivery stamps `emailed_at` on it, and the unique key is what lets the daily job run twice without sending twice. `due_date` is part of the key so that next cycle's reminder is a distinct event rather than a duplicate of this one.

All `*_at` fields are naive UTC `DATETIME` per §5.1.

---

## 8. Phase Plan

Each phase is one Spec Kit cycle: specify → plan → tasks → build → deploy.

### Phase 0 — Foundation

**Delivers:** the three-container Docker Compose stack; users, three roles, MySQL-backed sessions; **two-step login — password plus a six-digit code emailed via Gmail SMTP (§6.4)** — with rate limiting on login; **administrator account management — list, create with any role, edit, reset password, change role, deactivate and reactivate**; **a forced password change at first sign-in on any account an administrator set up (§6.4)**; the Canvas-like application shell (top nav, collapsible sidebar, dashboard placeholder) responsive from phone up; a seed script creating one administrator, one instructor, and five trainees; the project under version control.

**Why first:** everything depends on identity, and since look-and-feel ranks high in priorities, the shell should be right early rather than retrofitted. Getting the container topology right on day one avoids retrofitting deployment onto a working app — the more expensive order. Two-factor belongs here for the same reason: building it alongside session auth means the login path is written once, and there are no existing accounts to migrate onto it.

**Done when:** `docker compose up` on a clean machine brings up all three tiers; an administrator enters their password, receives a code by email, enters it, and reaches a styled dashboard; a wrong, expired, or already-used code is rejected; the administrator creates an account and that person is made to choose their own password at first sign-in; the last active administrator cannot switch themselves off; a seeded trainee sees a different navigation; the whole login flow is usable on a phone.

> **Sizing note.** Four to five weeks. Two-factor accounts for about half a week — the verify page, the mail path, rate limiting, and the negative-path tests. Administrator account management and the forced password change add roughly a further week.
>
> **Automated checks on every change are deferred.** Version control is established in this phase; running the tests automatically comes later. The tests themselves must be runnable on demand from the first commit.
>
> The full requirement set for this phase lives in `specs/001-platform-foundation/spec.md`, which is authoritative where it is more specific than this section.

---

### Phase 1 — Modules, Content & Registration

**Delivers:** administrator creates and publishes modules and assigns instructors; instructors view their module list and roster; trainees are registered and see their registered modules; module home page with left-hand navigation (an off-canvas drawer on phone). Plus the whole of §6.6 — ordered pages per module, the rich-text editor, server-side HTML sanitising, instructor image upload with its storage volume, and the trainee-facing content view.

**Why here:** the core object model — every later feature hangs off a module. Content belongs with it rather than in its own phase, because a module without material is not something an instructor can meaningfully publish, and the phase would otherwise end with software nobody can use for its actual purpose.

**Done when:** an administrator creates a module and assigns an instructor; that instructor writes three pages, reorders them, leaves one as a draft, uploads an image into another, and publishes; five trainees are registered and see exactly the two published pages; and a page body containing `<script>` is stored stripped, not escaped-on-render.

> **Sizing note.** Content authoring roughly doubles this phase, from about two weeks to four, making it the second largest after Quizzes. The editor, the sanitiser, and the upload path are each small; together they are not.

---

### Phase 2 — Quizzes

**Delivers:** question bank per module, quiz builder (**multiple choice only**), publish/availability windows, `passing_score` and a pass/fail outcome on every graded attempt, trainee attempt flow with save-as-you-go, auto-scoring, attempt review.

**Why here:** self-contained, high value, and it produces the scores Phase 3 consumes.

**Highest-risk area of the project.** See §11.

**Done when:** an instructor builds a ten-question quiz, three trainees take it — at least one on a phone — and correct scores appear immediately.

---

### Phase 3 — Results

**Delivers:** a trainee's own results view — every module they are registered on, their score, pass or fail, and current state; score history across attempts. Plus **an instructor's view of one module**: everyone registered on it, their state, and a way into any person's attempts.

The five states are **no test available · not started · in progress · passed · failed**. *Due* and *overdue* need a retake interval and therefore arrive with Phase 4; this phase settles the vocabulary they extend.

State is decided from a person's most recent submitted attempt at the module's **currently published** test. Attempts at a test that has since been replaced stay in their history but no longer count — so publishing a replacement resets everyone on that module.

**Replaces the gradebook.** There are no grade columns, no weights, no calculated final mark, and no manual grade entry. Everything is machine-scored, so there is nothing for an instructor to type in, and with terms gone there is no period for a final mark to conclude. What remains is the proposal's requirement to tell trainees "where they stand and what needs doing".

**Why here:** it needs attempts to exist, so it follows Phase 2. It adds no tables — everything it shows is derived from registrations and attempts already stored.

**Done when:** a trainee opens one page and sees every module they are on with a clear state against each; a trainee who has never taken a published test sees "not started" rather than a blank; a trainee sees nothing belonging to anyone else; and an instructor opens a module they run and sees who on it has not yet passed.

> **Schema checkpoint.** Per §5.3, the no-migrations principle is expected to expire at the end of this phase, when the first real module data appears. Decide then: Alembic, or hand-written `ALTER TABLE` scripts.

---

### Phase 4 — Scheduling & Notifications

**Delivers:** `Quiz.retake_interval_days` and `Quiz.completion_deadline_days` with owner-facing controls; computed due dates; the `Notification` model; an in-app notification list in the application shell; email delivery layered on the same rows; the in-process daily scheduler; all four triggers from §6.5.

**Why here:** every trigger needs something to notify *about* — registration exists after Phase 1, results after Phase 2, and the status vocabulary the notifications use is settled in Phase 3. This is the first genuinely cross-cutting phase, which is exactly why it is not an early one.

**Done when:** an owner sets a module to repeat every 90 days with a pass mark; a user who last *passed* it 91 days ago sees an overdue notice in-app and receives it in a digest email — and a user who merely failed an attempt yesterday is still overdue; a user overdue on three modules gets one digest, not three; running the scheduler a second time sends nothing; a newly registered user is notified; a graded attempt notifies its trainee; and the notification list is usable on a phone.

---

### Later candidates

Announcements · discussion boards · content pages within a module · CSV roster import · duplicating a module · an instructor-facing progress view.

---

## 9. Requirements by Role

### Administrator
- Create, edit, and deactivate user accounts; assign roles; reset passwords
- Cannot make any change that would leave the platform with no active administrator
- Create, publish, and unpublish modules
- Assign instructors to modules
- Register and deregister trainees, individually and in bulk

### Instructor
- View their own modules and rosters
- Maintain the module's question bank
- Build, edit, publish, and unpublish quizzes
- Set availability windows, time limits, attempt limits, and the pass mark
- Set how often a test must be retaken
- Register and deregister trainees on their own modules
- View trainee attempts and override auto-assigned scores

### Trainee
- View registered modules on a dashboard
- Open a module and see its navigation
- Take published quizzes within their availability window
- Resume an interrupted attempt
- See their own status per module: not started, passed, failed, due, or overdue
- Review their own past attempts and scores
- Receive notifications on registration, results, and when a test is due or overdue
- **Never** see another trainee's data

---

## 10. Non-Functional Requirements

**Security**
- Argon2 or bcrypt password hashing, never plain or fast hashes
- Every login requires a second factor: a six-digit code emailed to the account address. All roles, every login, no trusted-device exemption
- One-time codes stored hashed, not in plain text
- SMTP authenticated with a Google App Password held in `.env`, never an account password
- Instructor-authored HTML sanitised server-side before storage, never on render alone
- Uploads limited to images by extension, with a size cap; Nginx `client_max_body_size` and the application limit kept in agreement
- Authorisation checked in the service layer for every module-scoped action
- CSRF protection on all state-changing form posts
- Accounts are created only by an administrator or the seed script; no self-registration route for accounts exists
- A minimum password length of eight characters wherever a password is set
- A password issued by an administrator must be replaced by its owner at first sign-in
- Session cookies: `HttpOnly`, `Secure`, `SameSite=Lax`
- Rate limiting on login
- Database and backend unreachable from outside the Docker network
- Secrets from environment only; `.env` git-ignored, `.env.example` committed
- Nginx passes `X-Forwarded-Proto`; the backend trusts it for the `Secure` cookie flag

**Data integrity**
- Foreign key constraints enforced by InnoDB, not just the ORM
- Soft-delete for users and modules; hard delete only via administrator tooling
- MySQL data on a named Docker volume; a documented `mysqldump` backup command, to be run before any schema change once real data exists

**Notifications**
- Every notification exists as a stored row before any email is sent. Email is a delivery attempt on that row, never a substitute for it
- The daily job is idempotent: running it twice produces neither a second row nor a second email
- A user reads only their own notifications, scoped in the service layer like every other query
- The scheduler runs in-process and assumes exactly one `backend` replica

**Resilience — the critical one**
- A quiz attempt must survive a browser crash, tab close, connection loss, or a phone locking mid-attempt
- Answers persist to the server as the trainee progresses, not only on final submit
- Server-side clock governs time limits; the client clock is display only
- A resumed attempt shows remaining time calculated from `started_at`

**Presentation — responsive across all devices**

Bootstrap 5 is mobile-first; the work is in respecting that rather than fighting it.

| Width | Target | Layout |
|---|---|---|
| `< 576px` | phone | single column; top nav collapses to a hamburger; module nav becomes an off-canvas drawer; any wide table scrolls horizontally inside its own container |
| `576–992px` | tablet | two-column dashboard; module nav collapsible |
| `> 992px` | desktop | full Canvas-like layout: persistent left module nav, multi-column dashboard |

- Layout is verified at all three widths before a phase is called done. This is part of the definition of done, not a polish pass at the end.
- Touch targets no smaller than 44px; a quiz answer option is tappable across its whole row, not just its radio button.
- The page body never scrolls horizontally; wide content scrolls inside its own container.
- Accessible forms and keyboard navigation for the quiz-taking flow.
- Quiz taking is the flow most likely to happen on a phone, so it is designed phone-first and adapted upward. Instructor screens — the question bank and the roster — are the opposite: desktop-first, made survivable on a phone.

---

## 11. Known Risks

| Risk | Mitigation |
|---|---|
| **Quiz attempt state loss** — trainee loses connection or their phone locks during a timed quiz | Server-authoritative timing; incremental answer persistence; explicit `in_progress` state with resume path. Design this data model before writing Phase 2 code. |
| **Stale schema from no-migrations** — a model gains a field, `create_all()` ignores it, the app fails at runtime | Until first real use the fix is `docker compose down -v && docker compose up`. Document it as the default workflow so it becomes reflexive. Then the §5.3 expiry checkpoint. |
| **MySQL not ready when the backend starts** | Compose healthcheck with `condition: service_healthy`, plus connection retry in `database.py`. |
| **`utf8mb4` set too late** — fixing charset after tables exist is painful | Set it in Phase 0 on server, database, and connection URL; assert it in a startup check. |
| **Timezone handling in availability windows** | Store naive UTC in `DATETIME` everywhere; convert at the presentation layer only. MySQL will not catch this for you — it is a review item on every date field. |
| **Queries leaking into routers** now that repositories are gone | Constitution principle 1, enforced strictly: a router importing `select` or `Session` fails review. |
| **Leaking `password_hash`** via a table model used as a response or template context | Separate non-table read models; never return or render a `table=True` instance directly. |
| **Total lockout when Google is unreachable** — with 2FA on every login and no resend route, an SMTP outage or a revoked App Password stops everyone logging in. Accepted knowingly. | A hard `SMTP_TIMEOUT_SECONDS` so a failure is a fast clear error rather than a hung request; egress to `smtp.gmail.com:587` verified at deploy time, not first use; a password can be reset directly in the database if it ever comes to that. |
| **Burst email throttling** — a class of thirty logging in within a minute before a quiz | Google's daily cap is not the binding constraint; per-burst throttling is. The 10-minute code TTL means trainees can log in a few minutes ahead. If a class is ever throttled out, revisit the every-login rule for trainees specifically. |
| **Brute force of the code**, since there is no attempt counter | Rate limiting on the verify endpoint is the sole control and must not be removed or weakened without replacing it. Expiry alone does not bound guessing. |
| **A trainee who never passes is nagged indefinitely** — the cycle restarts only on a pass, so someone failing repeatedly stays overdue | Correct behaviour for mandatory training, and the digest holds it to one email a week. Unlimited retakes on recurring tests mean the trainee always has a way out, so it is never a locked state. Accepted limitation: nothing surfaces "who is persistently overdue" to the instructor, so a struggling trainee is visible only in their own inbox. |
| **A recurring quiz saved without a pass mark** would have no way to know when its cycle restarts | `passing_score` is required whenever `retake_interval_days` is set, validated when the owner saves the quiz rather than discovered by the scheduler at 06:00. |
| **Digest hides urgency** — one email listing five modules is easier to ignore than five emails | Accepted; the in-app list keeps one entry per module, and the digest leads with the count and the nearest due date. Revisit only if modules are genuinely being missed. |
| **Duplicate schedulers** if `backend` is ever run with more than one replica | The unique key on `Notification` degrades this to wasted work rather than double emails. Revisit properly *before* adding a replica, never after. |
| **Stored XSS through the content editor** — instructor-authored HTML is read back by every trainee who opens the page | Server-side sanitising before storage (§6.6). Sanitising in the editor or at render time only does not count. |
| **Malicious upload disguised as an image** | Extension allowlist and a size cap only. No content sniffing and no virus scanning — accepted, because uploads are limited to instructors, who are trusted staff. |
| **Orphaned images** accumulating when a page is edited or deleted | Module deletion removes its images; images unreferenced by any page are otherwise left in place. Accepted — a cleanup pass is straightforward later if the volume grows. |
| **Notification table growth** — four triggers, every user, every cycle, forever | Small at this scale, but it is the one table that grows without bound. Agree a retention rule when it first becomes noticeable. |
| **No forensic trail**, now that audit logging is out | Accepted. With one administrator and direct database access this is proportionate. If a second administrator is ever added, revisit — reconstructing who changed a grade is not possible after the fact. |
| **Email as a second factor is only as strong as the mailbox** | Accepted for a single small organisation where the administrator controls the Workspace accounts. Worth revisiting only if the threat model changes; the alternative is TOTP, which §3 currently excludes. |
| Scope creep toward full Canvas | The non-goals table in §3, enforced per phase |
| Auth shortcuts early | Session-based auth decided up front rather than migrated from JWT later |
| Responsive treated as a final polish pass | Three-width verification is in the definition of done for every phase (§10) |

---

## 12. Relationship to the Project Proposal

**This specification is the authority. The proposal was the starting document and is not a contract.** Where the two differ, this file is correct and the proposal is out of date. It is recorded here rather than left implicit, because the divergences are deliberate and will need explaining in the final report.

### Deliberate divergences

| Proposal said | This specification does | Why |
|---|---|---|
| Content delivered as static HTML pages, explicitly not stored in the database | Instructors author ordered pages inside the platform; content is stored in the database and edited through a rich-text editor (§6.6) | Content that only a developer can change is content nobody updates. An instructor must be able to fix a page without a deployment |
| Quizzes "pulled from the question bank", instructor picks a count | The instructor assembles a quiz from specific chosen questions | Simpler to build, review, and reason about. Nothing needs a random draw |
| Multiple-choice format, unspecified further | A question may have several correct options, scored all-or-nothing | "Select all the warning signs" is the natural shape of awareness questions |
| "A clear view of their own trainees' progress" for instructors | Not built. Instructors get a roster; each trainee sees their own status | Not required for the phases planned. Its absence is recorded as a limitation in §11 |
| "Basic notifications", displayed in-app | In-app list plus email, with a scheduler and digests (§6.5) | Recurring training is worthless if nobody is told a test is due |
| No grading detail | No gradebook at all — a results view instead | Everything is machine-scored and no period ever concludes |
| Waterfall methodology | Phased delivery, each phase shipping working software | Constitution Principle V. If the final report claims Waterfall, that claim needs correcting or this needs re-deciding |

### Still worth knowing

- The proposal's objective *"System availability: available at any time"* sits badly with two-factor authentication on every login through Gmail. §11 records this as the largest availability risk.
- The proposal's ethics section commits to protecting stored emails and scores and calls accountability essential. This specification carries no data-protection stance and no audit trail. If the report keeps those commitments, something here has to change.

---

## 13. Next Step

Write the **Phase 0 specification**: the three-container Compose stack, the user model, the three roles, MySQL-backed session authentication, the two-step emailed-code login of §6.4, the responsive application shell, and the seed script. That becomes the first Spec Kit cycle.
