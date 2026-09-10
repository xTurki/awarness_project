# Implementation Plan: Platform Foundation — Identity, Access & Shell

**Branch**: `001-platform-foundation` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-platform-foundation/spec.md`

## Summary

Stand up the three-container platform and everything to do with identity: accounts in three roles, two-step sign-in (password, then a six-digit code by email), server-side sessions with immediate revocation, administrator account management, a forced password change on any account an administrator set up, and the responsive application shell every later phase renders inside.

The technical approach is fixed by the project specification rather than open: FastAPI serving Jinja2 templates, SQLModel over MySQL 8, three containers behind Nginx, schema generated from the models with no migration tool. What this plan settles is the handful of implementation decisions that specification deliberately left to the phase — how to carry an in-progress sign-in between two requests, how to rate-limit without adding a fourth container, how to protect forms against cross-site posts when the login form has no session behind it yet, and how to run tests against a real MySQL rather than SQLite.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI · Jinja2 · SQLModel (over SQLAlchemy 2) · PyMySQL · argon2-cffi · pydantic-settings · itsdangerous · HTMX and Bootstrap 5 (vendored, not CDN)

**Storage**: MySQL 8, InnoDB, `utf8mb4`. Schema created from the models at startup; no migration tool (Constitution IV)

**Testing**: pytest against a disposable MySQL 8 container. SQLite is explicitly forbidden (Constitution VI)

**Target Platform**: Linux server running Docker Compose; browsers from 360px phone widths upward

**Project Type**: Server-rendered web application — three containers, one codebase, no separate frontend

**Performance Goals**: None specified beyond user-facing criteria in the spec — sign-in inside two minutes end to end, a code delivered inside sixty seconds, a mail failure reported inside fifteen. The platform serves one small organisation; throughput is not a design driver.

**Constraints**: Only Nginx publishes a port · backend and database unreachable from outside · secrets from the environment only · all timestamps naive UTC · single `backend` instance (no horizontal scaling anywhere in the design) · outbound egress to `smtp.gmail.com:587` required, and sign-in fails closed without it

**Scale/Scope**: One organisation, tens of accounts. Seven accounts at installation. Six user stories, 36 functional requirements, 13 success criteria.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked against `.specify/memory/constitution.md` v4.0.0.

### Principles

| # | Principle | Status | How this phase satisfies it |
|---|---|---|---|
| I | Routers Are Thin | ✅ | Routers parse the request, call one service function, render or redirect. `Session` and `select` appear only under `app/services/`. Enforced by done-gate 4. |
| II | Services Are HTTP-Agnostic | ✅ | `auth_service` and `email_service` take plain arguments and raise domain exceptions (`InvalidCredentials`, `InactiveAccount`, `CodeExpired`, `EmailDeliveryFailed`). No `Request`, `Response`, or `HTTPException` under `app/services/`. |
| III | Authorisation in the Service Layer | ✅ | Role checks live in the service functions, not in templates. This phase has no module-scoped data yet, so the rule applies to account administration: every function under `admin_service` takes the acting account and verifies its role. |
| IV | The Models Are the Schema | ✅ | `SQLModel.metadata.create_all()` in the startup lifespan. No Alembic. Model changes are applied by `docker compose down -v && up`. |
| V | Every Phase Ships Running Software | ✅ | The phase ends with a working sign-in an administrator can use to create real accounts. |
| VI | Tests Accompany the Feature | ✅ | Service tests written alongside each service, against a MySQL container. |
| VII | Non-Goals Are Defended | ✅ | Nothing outside the spec's Deliberately Excluded list is built. Self-registration, password self-reset, audit trail, and any second-factor channel other than email stay out. |
| VIII | Simplicity Is a Requirement | ✅ | Every decision in `research.md` was taken against "what is the least this needs". Three of them are recorded as *rejections* of the more capable option. |

### Constraints

| Constraint | Status | Note |
|---|---|---|
| Three tiers, only Nginx publishes a port | ✅ | |
| MySQL 8, InnoDB, `utf8mb4` everywhere | ✅ | Asserted at startup, not assumed |
| Naive UTC timestamps throughout | ✅ | |
| No `table=True` model returned or rendered | ✅ | Done-gate 5 |
| Argon2 for passwords; codes stored hashed | ✅ | Same hasher, separate call sites |
| Server-side sessions in MySQL; no JWT, no Redis | ✅ | |
| Session cookies `HttpOnly`, `Secure`, `SameSite=Lax`; login rate-limited | ✅ | Rate limiting in-process — see research R2 |
| CSRF on every state-changing form post | ✅ | Double-submit cookie — see research R3 |
| Secrets from environment, `.env` git-ignored | ✅ | |
| Mail sent inline in a worker thread under a hard timeout | ✅ | |
| Scheduled work in-process only | N/A | Nothing scheduled in this phase |

### Done gates for this phase

1. `docker compose up` on a clean checkout brings all three tiers to a working state
2. The test suite passes against a MySQL container
3. Layout verified below 576px, 576–992px, and above 992px
4. No module under `app/routers/` imports `Session` or `select`
5. No endpoint or template receives a `table=True` model instance
6. Every account-administration service function verifies the caller's role

**Result: PASS.** No violations, so Complexity Tracking below is empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-platform-foundation/
├── plan.md              # This file
├── research.md          # Phase 0 output — implementation decisions
├── data-model.md        # Phase 1 output — entities, constraints, transitions
├── quickstart.md        # Phase 1 output — bring it up and prove it works
├── contracts/
│   └── routes.md        # Phase 1 output — the HTTP surface
├── checklists/
│   └── requirements.md  # From /speckit-specify
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
docker-compose.yml
.env.example                     # committed; .env is not
nginx/
├── Dockerfile
└── nginx.conf                   # static + reverse proxy, X-Forwarded-Proto
backend/
├── Dockerfile
├── requirements.txt
├── seed.py                      # 1 administrator, 1 instructor, 5 trainees
└── app/
    ├── main.py                  # app factory, lifespan (create_all + charset assert)
    ├── config.py                # pydantic-settings
    ├── database.py              # engine, session dependency, connect retry
    ├── security.py              # hashing, token generation, CSRF, rate limiter
    ├── models/
    │   ├── user.py
    │   └── session.py
    ├── schemas/                 # non-table in/out models
    ├── services/
    │   ├── auth_service.py
    │   ├── admin_service.py
    │   └── email_service.py
    ├── routers/
    │   ├── auth.py
    │   ├── admin.py
    │   └── dashboard.py
    ├── dependencies.py          # current_account, require_role, require_password_set
    ├── templates/
    │   ├── base.html
    │   ├── auth/{login,verify,set_password}.html
    │   ├── admin/{list,form}.html
    │   ├── dashboard.html
    │   ├── emails/login_code.txt
    │   └── components/
    └── static/{css,js}          # vendored Bootstrap + HTMX
tests/
├── conftest.py                  # MySQL container fixture
├── services/                    # the bulk
└── routers/
```

**Structure Decision**: The layout is fixed by `lms-project-spec.md` §6.2 and is followed exactly. Two files are added that the project specification did not name: `app/security.py`, which holds the three cross-cutting primitives decided in research (hashing, CSRF, rate limiting) so they are not scattered, and `app/dependencies.py`, which holds the FastAPI dependencies that guard routes — kept out of `services/` because they touch `Request` and Principle II forbids that in the service layer.

`app/cli.py` from the project specification is **not** created: the break-glass command it held was removed when the security surface was reduced.

## Complexity Tracking

No constitution violations. Nothing to justify.
