# Implementation Plan: Results — Where Everyone Stands

**Branch**: `004-results` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-results/spec.md`

## Summary

Two pages. A trainee opens one and sees every module they are on with a state against each. An instructor opens the other and sees everyone on their module with the same states.

**This phase stores nothing.** Every figure it shows already exists in registrations and attempts. The work is one query and one function that turns rows into a state — plus two templates and the ordering that puts outstanding things first.

The one piece worth designing carefully is the state function itself, because Phases 2, 3, and 4 all have to agree on what "passed" means for the same person.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Nothing new

**Storage**: Nothing new. No tables, no columns, no volume.

**Testing**: pytest against a disposable MySQL container

**Target Platform**: Unchanged

**Project Type**: Server-rendered web application, three containers

**Performance Goals**: A results page loads without noticeable delay for a person on thirty modules (SC-008), and an instructor's list for a module with thirty people. Both mean one query, not one per row.

**Constraints**: Nothing may be stored · state comes from the most recent submitted attempt at the **currently published** test only · no view spans more than one module · every state must be legible without colour

**Scale/Scope**: Four user stories, 27 functional requirements, 15 success criteria. Zero new tables.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked against `.specify/memory/constitution.md` v4.0.0.

| # | Principle | Status | How this phase satisfies it |
|---|---|---|---|
| I | Routers Are Thin | ✅ | Two routes, each parsing an id and calling one service function. |
| II | Services Are HTTP-Agnostic | ✅ | `results_service` returns plain view objects; the state function takes rows and returns an enum. |
| III | Authorisation in the Service Layer | ✅ | A person sees only their own; an instructor's view resolves through `module_service.get_for`. |
| IV | The Models Are the Schema | ✅ | Nothing added, so nothing to create. |
| V | Every Phase Ships Running Software | ✅ | Ends with both pages working against real attempts from Phase 2. |
| VI | Tests Accompany the Feature | ✅ | The state function is pure and gets a table of cases covering all five states. |
| VII | Non-Goals Are Defended | ✅ | No gradebook, no certificate, no export, no charts, no organisation-wide view. |
| VIII | Simplicity Is a Requirement | ✅ | The strongest case in the project: the simplest thing that works is to store nothing, and that is what FR-025 requires. |

### Constraints

| Constraint | Status |
|---|---|
| No new stored record of a result (FR-025) | ✅ |
| Naive UTC everywhere | ✅ |
| No `table=True` model rendered | ✅ |
| Authorisation in the service layer | ✅ |
| No view spanning more than one module (FR-021) | ✅ |

### Done gates for this phase

1. `docker compose up` brings all three tiers to a working state
2. The test suite passes against a MySQL container
3. Layout verified below 576px, 576–992px, above 992px
4. No module under `app/routers/` imports `Session` or `select`
5. No endpoint or template receives a `table=True` model instance
6. Every module-scoped service function performs its own authorisation check

**Result: PASS.** Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/004-results/
├── plan.md
├── research.md
├── data-model.md        # derivation rules — no tables in this phase
├── quickstart.md
├── contracts/routes.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks output — not created here
```

### Source Code (repository root)

```text
backend/app/
├── services/
│   ├── results_service.py   # new — the two queries
│   └── state.py             # new — one pure function: rows in, state out
├── routers/
│   └── results.py           # new — four routes; `GET /` moves here from dashboard.py,
│                             # which is then deleted (there is exactly one `GET /`)
└── templates/results/
    ├── dashboard.html       # a trainee's dashboard = their results
    ├── module.html          # one module's history for one person
    └── cohort.html          # an instructor's view of one module

tests/services/{test_state,test_results}.py
```

**Structure Decision**: `app/services/state.py` holds one pure function that decides a person's state for a module. It is separate from `results_service` for the same reason `scoring.py` was separated in Phase 2 — it is the piece with the most cases, it touches nothing, and **Phase 4 will import it** to decide who is due. Putting it anywhere else would mean Phase 4 either duplicates the rule or reaches into a service that queries the database.

## Complexity Tracking

No constitution violations. Nothing to justify.
