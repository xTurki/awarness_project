# Specification Quality Checklist: Results — Where Everyone Stands

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-10
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

**All 16 items pass.** 26 functional requirements, 4 prioritised user stories, 14 measurable success criteria, 9 edge cases. Still the smallest phase, and still the only one that stores nothing — the instructor view is derived from the same registrations and attempts as the trainee's own.

### An inconsistency between phases, resolved without asking

The project specification listed this phase's states as *not started · passed · failed · due · overdue*. But "due" and "overdue" are computed from a retake interval that arrives in Phase 4, so two of the five could not be produced by anything this phase builds.

The dependency forces the answer, so it was resolved rather than raised: this phase delivers the five it can compute — **no test available · not started · in progress · passed · failed** — and Phase 4 adds the two that need a schedule. "In progress" was added because Phase 2 worked hard to make an interrupted attempt survivable and nothing else lets a trainee find it again.

### Both clarifications resolved

- **State follows the currently published test.** Attempts at a replaced test stay in a person's history but no longer count towards their state.
- **An instructor sees one module's people; an administrator sees nothing across the organisation.** A new user story and six requirements cover the instructor view.

### The consequence that needs an interface warning

Deciding state from the currently published test means **replacing a test resets everyone on that module to "not started"** — including people who passed the old version yesterday. Correcting one misspelled question invalidates the whole group's record, and once Phase 4 exists it makes all of them due at once and notifies all of them.

That is the honest reading of "the module now asks something different", and it puts real weight behind getting a test right before publishing. But an instructor must know it before they click, so the specification requires the platform to warn them what publishing a replacement will do.

### Still open across the project

Nobody can answer "how many of our staff have completed their training?" in one place. The instructor view covers one module at a time and there is no administrator view spanning the organisation. Recorded in the excluded list so it reads as a decision.

Spec is ready for `/speckit-plan`.
