# Specification Quality Checklist: Modules, Content & Registration

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

`.specify/memory/constitution.md` was amended to match and is now at 3.0.0 — a MAJOR bump, since mandatory rules were removed.

### Consequences worth knowing

- **Anyone can learn whether an email address has an account**, by watching how the sign-in form responds. Accepted.
- **A mail outage locks everyone out**, with no command-line way back in. Recovery would mean editing the database directly.
- **An account disabled between the password step and the code step can still complete that sign-in.** The window is minutes.

None of these matters much for one small organisation. They are recorded so that nobody later mistakes their absence for an oversight.

### Phase 1 shape after the reduction

35 functional requirements, 4 prioritised user stories, 14 measurable success criteria, 10 edge cases.

Three further simplifications were settled after the first draft and propagated to the project specification, now at v12:

- **Modules are never archived.** Published or unpublished; retiring one means unpublishing it.
- **Registrations carry no status.** A person is on a module or is not.
- **Self-registration is gone entirely.** `Module.self_registration_open` is removed along with a whole user story and three requirements. This closed a real contradiction: a trainee was permitted to put themselves on a module while the dashboard showed only modules they were already on, so there was no way to discover one. Rather than add a browse-and-join page, the capability was dropped — mandatory training is assigned, not opted into.
- **`Module.code` is removed.** Inherited from the school framing, never used, never explained.

Uploads are now checked by extension and size only. Content sanitising before storage is the one security control kept in this phase, because instructor-authored HTML is read back by every trainee who opens the page.

Spec is ready for `/speckit-plan`.
