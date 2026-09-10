# Implementation Plan: Scheduling & Notifications

**Branch**: `005-scheduling-notifications` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-scheduling-notifications/spec.md`

## Summary

An instructor sets how often a test must be retaken. From then on the platform works out who is due, tells them before it lapses and while it is lapsed, and keeps doing so — with nobody signed in and nobody remembering to check.

This is the only part of the platform that acts on its own, so most of the design is about **running the same job twice being harmless**. One table, one daily job, one extra field on `test`, and the two states Phase 3 left for this phase to add.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `APScheduler` — the only addition, and the only new dependency since Phase 1

**Storage**: MySQL 8 — one new table, two new columns on `test`. No new volume.

**Testing**: pytest against a disposable MySQL container. The daily job is a plain function, so tests call it directly rather than waiting for a scheduler.

**Target Platform**: Unchanged. **Assumes exactly one `backend` instance** — two would mean two schedulers.

**Project Type**: Server-rendered web application, three containers

**Performance Goals**: The daily job completes for tens of people across tens of modules well inside a minute. Nothing here is on a request path except the notification list.

**Constraints**: Due dates derived, never stored · the same rule as Phases 2 and 3 decides what represents a person · a notification record exists before any message is sent · running the job twice changes nothing · no queue, no worker container, no second machine

**Scale/Scope**: Four user stories, 40 functional requirements, 17 success criteria. One new table.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked against `.specify/memory/constitution.md` v4.0.0.

| # | Principle | Status | How this phase satisfies it |
|---|---|---|---|
| I | Routers Are Thin | ✅ | Two routes for the notification list. The daily job is not a route at all. |
| II | Services Are HTTP-Agnostic | ✅ | `notification_service` and `due_service` take plain arguments. The job function takes a session and a date. |
| III | Authorisation in the Service Layer | ✅ | A person reads only their own notifications; setting an interval resolves through `module_service.get_for`. |
| IV | The Models Are the Schema | ✅ | One table and two columns from `create_all()`. |
| V | Every Phase Ships Running Software | ✅ | Ends with a real reminder arriving by email and appearing in the app. |
| VI | Tests Accompany the Feature | ✅ | Due-date computation and job idempotency both get their own test modules. |
| VII | Non-Goals Are Defended | ✅ | No notification preferences, no unsubscribe, no channel beyond in-app and email, no escalation, no manager. |
| VIII | Simplicity Is a Requirement | ✅ | One dependency, in-process. Research records what was rejected. |

### Constraints

| Constraint | Status | Note |
|---|---|---|
| Scheduled work runs in-process in `backend` | ✅ | Constitution permits exactly this, and forbids a broker or worker container |
| Assumes one `backend` replica | ✅ | Stated in the constitution; recorded again in research R6 |
| A notification record exists before any message | ✅ | FR-021 |
| One message may cover several records, stamping all of them | ✅ | FR-019, FR-023 |
| The in-app list stays granular where messages were combined | ✅ | FR-034 |
| The job is idempotent by constraint, not by bookkeeping | ✅ | Research R5 |
| Naive UTC everywhere | ✅ | The whole phase is dates |

### Done gates for this phase

1. `docker compose up` brings all three tiers to a working state
2. The test suite passes against a MySQL container
3. Layout verified below 576px, 576–992px, above 992px
4. No module under `app/routers/` imports `Session` or `select`
5. No endpoint or template receives a `table=True` model instance
6. Every module-scoped service function performs its own authorisation check

> **Scope of gate 6 in this phase.** The gate governs functions a caller can reach. `daily_job.run_daily` and `due.py` are reached by neither — **no route invokes them**, the scheduler calls the job and tests call it directly, and it acts with system authority over every registration by design. There is nothing for them to authorise against, so the gate does not apply to them. It applies in full to everything else this phase adds: setting a schedule resolves through `module_service.get_for`, and a person reads only their own notifications.

**Result: PASS.** Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/005-scheduling-notifications/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/routes.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks output — not created here
```

### Source Code (repository root)

```text
backend/
├── requirements.txt              # + APScheduler
└── app/
    ├── main.py                   # lifespan also starts the scheduler
    ├── config.py                 # + DUE_SOON_LEAD_DAYS, SCHEDULER_HOUR_UTC
    ├── models/
    │   └── notification.py       # new
    ├── services/
    │   ├── due.py                # new — pure: given a test, registration, attempts, return the due date
    │   ├── state.py              # from Phase 3 — extended with due and overdue
    │   ├── notification_service.py  # new — create, list, mark seen
    │   └── daily_job.py          # new — the whole scheduled run, one function
    ├── routers/
    │   └── notifications.py      # new — two routes
    └── templates/
        ├── notifications/list.html
        ├── components/nav_badge.html
        └── emails/{digest,registered,result}.txt

tests/services/{test_due,test_daily_job,test_notification}.py
```

**Structure Decision**: Two additions follow the pattern set in Phases 2 and 3.

`app/services/due.py` is a pure function alongside `scoring.py` and `state.py` — given a test, a registration, and that person's attempts, return their due date or `None`. No session, no clock passed implicitly. Due-date arithmetic has the most cases in this phase and is the easiest thing to get subtly wrong.

`app/services/daily_job.py` holds the scheduled run as **one ordinary function taking a session and a date**. The scheduler calls it; tests call it directly with a fixed date and call it twice to prove nothing happens the second time. Nothing about the job requires a scheduler to be running to test it.

## Complexity Tracking

No constitution violations. Nothing to justify.
