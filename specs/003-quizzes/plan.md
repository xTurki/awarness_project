# Implementation Plan: Quizzes — Question Banks, Attempts & Scoring

**Branch**: `003-quizzes` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-quizzes/spec.md`

## Summary

An instructor writes multiple-choice questions for their module, assembles them into a test with a pass mark, and publishes it. A trainee takes it and gets a score straight away.

The engineering work is almost entirely in one place: **the attempt**. Answers must be saved as they are given rather than on submit, the deadline and the question order must be fixed when the attempt starts, and remaining time must come from the server. Get those four things right and the rest of the phase is forms and queries.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Nothing new. Everything this phase needs already exists from Phases 0 and 1.

**Storage**: MySQL 8 — five new tables. No new volume; nothing here stores files.

**Testing**: pytest against a disposable MySQL container, as before

**Target Platform**: Unchanged

**Project Type**: Server-rendered web application, three containers

**Performance Goals**: A submitted test scores and displays within two seconds (SC-002). Saving one answer must feel instant, since it happens on every click.

**Constraints**: An attempt's deadline and question order never change once it starts · time remaining comes from the server clock only · each answer is its own write · scoring is exact-match with no partial credit · a test cannot be edited once anyone has attempted it

**Scale/Scope**: Five user stories, 39 functional requirements, 14 success criteria. Five new tables. The largest phase in the project.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked against `.specify/memory/constitution.md` v4.0.0.

| # | Principle | Status | How this phase satisfies it |
|---|---|---|---|
| I | Routers Are Thin | ✅ | `Session` and `select` stay under `app/services/`. The answer-save route is one line of parsing and one service call. |
| II | Services Are HTTP-Agnostic | ✅ | `attempt_service` takes ids and values, returns plain data, raises domain exceptions (`AttemptClosed`, `NoAttemptsLeft`, `OutsideWindow`). |
| III | Authorisation in the Service Layer | ✅ | Every function resolves the module through Phase 1's `module_service.get_for`, then checks the attempt belongs to the caller. |
| IV | The Models Are the Schema | ✅ | Five tables from `create_all()`. Still no migration tool. |
| V | Every Phase Ships Running Software | ✅ | Ends with an instructor able to publish a real test and trainees able to take it and see scores. |
| VI | Tests Accompany the Feature | ✅ | Against MySQL. Scoring and the attempt lifecycle carry the most tests, because they are where being wrong is silent. |
| VII | Non-Goals Are Defended | ✅ | Multiple choice only. No partial credit, no random draw from the bank, no question types that need a human marker. |
| VIII | Simplicity Is a Requirement | ✅ | No new dependencies. Research records what was rejected. |

### Constraints

| Constraint | Status |
|---|---|
| Naive UTC everywhere — the whole phase is about time | ✅ |
| No `table=True` model rendered or returned | ✅ |
| Authorisation in the service layer | ✅ |
| Three tiers, only Nginx published | ✅ |
| No queue, no worker, no second machine | ✅ |

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
specs/003-quizzes/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/routes.md
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks output — not created here
```

### Source Code (repository root)

Additions to what Phases 0 and 1 built.

```text
backend/app/
├── models/
│   ├── question.py          # new — question + answer option
│   ├── test.py              # new — the test and its question list
│   └── attempt.py           # new — attempt + answer given
├── services/
│   ├── question_service.py  # new — the bank
│   ├── test_service.py      # new — building, publishing, the frozen check
│   ├── attempt_service.py   # new — start, save, resume, submit, score
│   └── scoring.py           # new — one pure function, no database
├── routers/
│   ├── questions.py         # new
│   ├── tests.py             # new
│   └── attempts.py          # new
└── templates/
    ├── questions/{list,form}.html
    ├── tests/{list,form,detail}.html
    └── attempts/{take,review,list}.html

tests/services/{test_question,test_test,test_attempt,test_scoring}.py
```

**Structure Decision**: Phases 0 and 1 layout continues. One addition worth naming: `app/services/scoring.py` holds a single pure function — given the questions and the answers given, return the score. No database, no session, no clock. It is the piece most worth testing exhaustively and easiest to test when it touches nothing.

## Complexity Tracking

No constitution violations. Nothing to justify.
