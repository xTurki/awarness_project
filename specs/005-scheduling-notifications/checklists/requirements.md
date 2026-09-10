# Specification Quality Checklist: Scheduling & Notifications

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

**All 16 items pass.** 40 functional requirements, 4 prioritised user stories, 17 measurable success criteria, 11 edge cases.

This is the only phase in which the platform acts without anyone asking it to, which is why a quarter of its requirements exist purely to make a repeated, missed, or interrupted run harmless.

### The three clarifications, resolved

**A conflict between documents, now settled.** The project specification ran the retake clock from a person's most recent *passing* attempt, while Phases 2 and 3 had already decided the most recent attempt *of any kind* represents them. The clock now runs from the most recent attempt and only if it passed — one rule across the whole platform. `lms-project-spec.md` was corrected to match and is at v14.

**A replacement test notifies everyone it made due**, with no grace period. The instructor is already warned before publishing what it will do.

**A one-off test may carry a completion period** — "pass this within thirty days of being registered". This closes a gap the phase plan never covered: mandatory training assigned once was never chased, however long someone left it. It reuses the entire due-date and reminder mechanism rather than adding a second one, and stays optional, so a genuinely optional module can still be left unchased.

### The consequence that will be noticed

Running the clock from the most recent attempt means someone who passed, then retook the test to revise and scored below the pass mark, is **due immediately and overdue the next day** — and gets an email about it. The platform is at least consistent, since Phases 2 and 3 already work this way, and Phase 2's review makes passing again straightforward. But casual revision now has a cost, and people will notice it. Recorded in Assumptions rather than left to be discovered.

### Content Quality note

Implementation names were kept out deliberately. The requirements describe "a process that runs once a day without anyone signed in" rather than naming a scheduler, and "a notification record" rather than a table. FR-030 states the constraint that actually matters — no second machine, no separate service — as an outcome.

Concrete values that shape the experience — a fourteen-day warning, a single overdue notice, an early-morning run, opening the list marking it read, notifications never deleted — sit in Assumptions with the reasoning for each.

### One thing worth seeing before planning

An overdue test is announced once and never repeated; what persists is the state, not the messaging. Someone who never passes therefore stops hearing about it, and nobody but that person sees the state unless an instructor opens the module view from Phase 3. Recurring tests allow unlimited attempts, so there is always a route out.

Spec is ready for `/speckit-plan`.
