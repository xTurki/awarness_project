# Specification Quality Checklist: Platform Foundation, Identity, Access & Shell

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

**All 16 items pass.**

### Scope was deliberately reduced

The project owner asked for the security surface to be cut back, on the grounds that this is a small project. Reviewing what had accumulated, most of it had been added without being asked for, and it has been removed.

**Removed**: the break-glass command; binding a pending sign-in to the browser that started it; identical failure messages for unknown email, wrong password, and disabled account; re-checking that an account is still active at the code step; rate limiting on code entry; the ban on codes reaching logs; upload content-sniffing, generated filenames, and non-executing serving; the rule that a new password must differ from the administrator's; and the guard against removing the last administrator. The minimum password length drops from ten characters to eight.

**Kept**, because removing them costs more than it saves: password hashing; server-side sessions with immediate revocation; authorisation checked in the service layer, which is what keeps one trainee out of another's data; server-side sanitising of instructor-authored HTML before storage; CSRF; secrets from the environment; and rate limiting on sign-in.

The two-step sign-in itself stays, simplified: password, then a six-digit emailed code valid for ten minutes and usable once. The verify form carries the email address, so no signed cookie is needed between the steps.

`.specify/memory/constitution.md` was amended to match and is now at 3.0.0, a MAJOR bump, since mandatory rules were removed.

### Consequences worth knowing

- **Anyone can learn whether an email address has an account**, by watching how the sign-in form responds. Accepted.
- **A mail outage locks everyone out**, with no command-line way back in. Recovery would mean editing the database directly.
- **An account disabled between the password step and the code step can still complete that sign-in.** The window is minutes.
- **Nothing throttles code entry.** A six-digit code is one of a million and its ten-minute life is the only bound on guessing. An attacker who already has the password could work through them.

None of these matters much for one small organisation. They are recorded so that nobody later mistakes their absence for an oversight.

### Phase 0 shape after the reduction

36 functional requirements, 6 prioritised user stories, 13 measurable success criteria, 10 edge cases. Account creation is administrator-only; a password an administrator sets must be replaced by its owner at first sign-in.

### Re-checked after the reduction

The removals were surgical, so the specification was re-read end to end. Five inconsistencies had been left behind and are now fixed:

- A success criterion still refused a code "belonging to a different sign-in", the browser binding that made that possible was removed.
- An edge case claimed repeated wrong codes were throttled, while the requirement it rested on now covers sign-in only.
- An assumption made the same claim.
- A requirement to end all of an account's sessions at once had no user story, no acceptance scenario, and no success criterion attached to it. Removed rather than given scaffolding it did not need.
- The overview said the phase contains "no tests", which reads as automated tests. It means no quizzes.

`.specify/memory/constitution.md` also still required the break-glass command that 3.0.0 had deleted, and required it to keep working. Corrected at 3.0.1.

Spec is ready for `/speckit-plan`.
