# Specification Quality Checklist: Quizzes — Question Banks, Attempts & Scoring

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

**All 16 items pass.** 39 functional requirements, 5 prioritised user stories, 14 measurable success criteria, 10 edge cases.

### The three clarifications, resolved

- **A test is frozen from its first attempt.** No adding, removing, reordering, rewording, or changing the pass mark once anyone has sat it. An instructor who needs something different builds a new test and unpublishes the old one.
- **The most recent attempt represents a person** — for their score, their outcome, and anything Phase 3 displays or Phase 4 measures a retake interval from. Earlier attempts stay visible in their history.
- **A review shows the correct answers**, not only which questions were wrong.

The first of these made an earlier requirement redundant. "Score an attempt against the questions it was shown, even if the test has since changed" existed to handle a test changing under people's feet; a test can no longer change, so the requirement was removed rather than left as dead weight. The edge case it covered was rewritten to describe what an instructor actually does now.

### One consequence recorded in the specification

The last two decisions interact. A trainee can fail, read the correct answers, retake, and pass — and in Phase 4, where recurring tests allow unlimited retakes, that route is always open. The pass mark therefore establishes that someone has seen the right answers and can reproduce them, not that they knew them unaided.

For awareness training that is defensible, arguably even the point. It is written into the Assumptions section so that it reads as a choice rather than a hole somebody missed.

### Three requirements carry most of the phase's risk

FR-015, FR-016, and FR-017: an attempt's ending moment and its question order are fixed when it begins and never change, and each answer is recorded as it is given rather than on submission. Together they are what makes an interrupted attempt survivable — cheap at the start, expensive to retrofit. FR-019 belongs with them: time remaining is decided by the platform, and any countdown on the trainee's device is decoration.

### Content Quality note

Concrete values that shape the experience — scores as percentages, shuffling reordering questions rather than options, one attempt in progress at a time, a test frozen at first attempt — sit in Assumptions with the reasoning for each rather than inside the requirements.

Spec is ready for `/speckit-plan`.
