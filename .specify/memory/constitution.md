<!--
SYNC IMPACT REPORT — v4.0.0 (current)
=====================================
Version change: 3.0.1 → 4.0.0
Bump rationale: MAJOR. A mandatory rule was REMOVED — the requirement that a
mysqldump precede any schema change against an instance holding real data.
Removals are backward-incompatible governance changes under this constitution's
own policy, the same reasoning applied at 2.0.0.

Trigger: the owner decided there is no backup of any kind. A rule requiring a
backup before a schema change cannot stand when no backup mechanism exists.

Removed from Governance → Scheduled amendments:
  - the mysqldump-before-schema-change requirement

Replaced with a plain statement of the consequence: a schema change against
real data risks that data with nothing to fall back on.

Two further owner decisions recorded in the specifications rather than here,
since the constitution carried no rule on either:
  - the interface is English, left-to-right only
  - there is no application logging beyond what the server prints

Principles: all eight unchanged in name, number, and meaning.

Prior reports retained below for history.

SYNC IMPACT REPORT — v3.0.1
===========================
Version change: 3.0.0 → 3.0.1
Bump rationale: PATCH. Corrects a rule that contradicted 3.0.0 itself. No
meaning changed anywhere else.

The Email section still required a server-side break-glass for issuing a login
code, and required it to "remain working" — but 3.0.0 removed that command. The
rule now states the actual consequence: with neither a resend route nor a
bypass, a mail outage locks everyone out until mail is restored, so outbound
reachability must be verified at deployment.

Found while re-checking the phase specifications after the 3.0.0 reduction.

Prior reports retained below for history.

SYNC IMPACT REPORT — v3.0.0
===========================
Version change: 2.2.1 → 3.0.0
Bump rationale: MAJOR. Mandatory rules were REMOVED, which is a backward-incompatible
governance change under this constitution's own versioning policy — the same
reasoning applied to the audit-log removal at 2.0.0.

Trigger: the project owner asked for the security surface to be reduced, on the
grounds that this is a small project and the hardening had grown out of
proportion to it. Reviewing what had accumulated, most of it had been added
without being asked for. That is the material being removed.

Removed from Technology & Security Constraints → Security:
  - identical failure responses for unknown email / wrong password / disabled
    account (account-enumeration protection)
  - re-verification of is_active at the code step
  - rate limiting on code verification (rate limiting on login itself is kept)
  - the pending-login cookie and its requirements
  - the prohibition on codes reaching logs, templates, and error messages
  - the requirement that codes be generated with `secrets`

Removed from Development Workflow & Quality Gates:
  - gate 7 (no plaintext code in HTML or logs, asserted by test)
  - gate 8 (scheduled job idempotency, asserted by test)

Retained deliberately, because removing them costs more than it saves:
  password hashing; server-side sessions; authorisation in the service layer
  (Principle III, which is what keeps one trainee out of another's data);
  server-side sanitising of instructor-authored HTML; CSRF; secrets from the
  environment; rate limiting on login.

Principles: all eight unchanged in name, number, and meaning. The idempotency
constraint under Scheduling and notifications is kept as a functional rule —
sending someone the same reminder twice is a defect, not a security control.

Prior reports retained below for history.

SYNC IMPACT REPORT — v2.2.1
===========================
Version change: 2.2.0 → 2.2.1
Bump rationale: PATCH. Terminology only. Every rule keeps its meaning, its
force, and its number; only the nouns changed. No principle added, removed, or
redefined, and nothing built under 2.2.0 becomes non-compliant.

Trigger: the project was reframed from a school LMS to an SME cybersecurity
awareness platform, at the owner's direction, to match the project proposal.
Terms were removed from the domain entirely.

Renames applied throughout: Course→Module, Enrollment→Registration,
teacher→instructor, student→trainee, admin→administrator, school→organisation.
Principle III and done-gate 6 now read "module-scoped" where they read
"course-scoped"; the constraint is identical.

Note on why PATCH and not MINOR: renaming a noun does not expand, narrow, or
add guidance. A reader of 2.2.0 and a reader of 2.2.1 are held to exactly the
same rules. Compare the 2.1.0 entry below, where a prohibition was genuinely
lifted, and 2.0.0, where a requirement was genuinely removed.

Not governed here, recorded for context: the specification dropped the
gradebook (GradeColumn, GradeEntry, weighting, final marks) in favour of a
results view. The constitution never carried a gradebook rule, so nothing here
changed as a result.

Prior reports retained below for history.

SYNC IMPACT REPORT — v2.2.0
===========================
Version change: 2.1.0 → 2.2.0
Bump rationale: MINOR. Guidance expanded, no rule removed. Nothing built under
2.1.0 becomes non-compliant.

Trigger: two owner decisions taken after 2.1.0 was written.
  1. The recurrence cycle now restarts when a test is PASSED, not merely taken.
     A passing_score is therefore required on any quiz carrying a retake
     interval. This closes the loophole where a deliberately failed attempt
     cleared an overdue state.
  2. Due and overdue mail is batched into one digest per user per run, rather
     than one email per module. This broke the previous one-email-per-row
     wording, which had assumed a 1:1 mapping.

Modified sections:
  Technology & Security Constraints → Scheduling and notifications :
      delivery rule reworded for 1:many; new rule added requiring that a batched
      email stamp every row it covered and that grouping never reduce what the
      in-app list shows; idempotency rule tightened to name the two mechanisms
      (uniqueness constraint, unstamped-row selection) and to forbid relying on
      last-run bookkeeping.

Added principles: none.  Removed rules: none.
Deferred items / follow-up TODOs: none.

Open point carried in the specification, not here: nothing surfaces persistently
overdue users to a module owner. Flagged as a risk, not assumed as scope.

Prior reports retained below for history.

SYNC IMPACT REPORT — v2.1.0
===========================
Version change: 2.0.0 → 2.1.0
Bump rationale: MINOR. Guidance materially expanded; a prohibition was lifted and
replaced with tighter conditions. No principle changed, and nothing built under
2.0.0 becomes non-compliant — a system with no scheduler still satisfies 2.1.0.

Note on why this is MINOR where the 2.0.0 audit change was MAJOR: removing the
audit requirement took a capability OUT of the system, so work done under 1.1.0
(writing audit entries) became wrong. Lifting the scheduler ban ADDS a permitted
capability under new obligations. Additions do not invalidate prior work;
removals do. That is the line this project draws between MINOR and MAJOR.

Trigger: recurring test schedules and notifications added to the specification
(§6.5), at the owner's direction, to satisfy requirements the earlier draft did
not cover. Due and overdue notices must fire with nobody logged in, which the
previous blanket ban on a scheduler made impossible.

Modified sections:
  Technology & Security Constraints → Email      : scheduler permitted in-process;
                                                   mail scope widened from login
                                                   codes to named triggers
  Technology & Security Constraints → Scheduling and notifications : new (4 rules)
  Development Workflow & Quality Gates           : gate 8 added

Added principles: none.  Removed rules: none.
Deferred items / follow-up TODOs: none.

Open point carried in the specification, not here: recurrence resets when a test
is taken, not when it is passed. Changing that needs a passing score on Quiz and
has not been assumed.

Prior reports retained below for history.

SYNC IMPACT REPORT — v2.0.0
===========================
Version change: 1.1.0 → 2.0.0
Bump rationale: MAJOR. A mandatory governance rule was REMOVED, which is a
backward-incompatible governance change under this constitution's own versioning
policy. The removed rule is the audit-log requirement ("Every destructive action
MUST be written to an audit log"), struck at the project owner's direction. No
principle was removed; all eight stand unchanged in name, number, and meaning.

Two-factor authentication remains required, but its mechanism was simplified at
the owner's direction: the pending code now lives in two nullable columns on the
User row rather than in a challenge table, and the resend route is gone.

Modified sections:
  Technology & Security Constraints → Security : audit rule REMOVED;
                                                 rate-limit rule narrowed
                                                 (resend endpoint no longer exists)
  Technology & Security Constraints → Email    : audit clause removed from the
                                                 break-glass rule
Removed rules: audit logging (1), resend rate limiting (folded into the above).
Added principles: none.  Added sections: none.
Deferred items / follow-up TODOs: none.

Consequence worth recording: with auditing gone there is no forensic trail. A
grade change cannot be attributed after the fact. This is proportionate for a
single-administrator organisation and is recorded as an accepted risk in the specification,
not as an oversight.

Prior reports retained below for history.

SYNC IMPACT REPORT — v1.1.0
===========================
Version change: 1.0.0 → 1.1.0
Bump rationale: MINOR. Two-factor authentication added to the constraints
section: five Security rules, a new Email subsection, and done-gate 7. No
principle changed.

SYNC IMPACT REPORT — v1.0.0
===========================
Version change: (unversioned scaffold) → 1.0.0
Bump rationale: Initial ratification. The previous file was the unmodified core
template with every placeholder unfilled, so there is no prior governance to
compare against; this is a first adoption rather than an amendment.

Principles defined (all newly created from lms-project-spec.md §1):
  [PRINCIPLE_1_NAME] → I. Routers Are Thin (NON-NEGOTIABLE)
  [PRINCIPLE_2_NAME] → II. Services Are HTTP-Agnostic
  [PRINCIPLE_3_NAME] → III. Authorisation Lives in the Service Layer (NON-NEGOTIABLE)
  [PRINCIPLE_4_NAME] → IV. The Models Are the Schema (TIME-LIMITED)
  [PRINCIPLE_5_NAME] → V. Every Phase Ships Running Software
  (added beyond template) → VI. Tests Accompany the Feature
  (added beyond template) → VII. Non-Goals Are Defended
  (added beyond template) → VIII. Simplicity Is a Requirement

Template deviation: the resolved scaffold provides five principle slots; the
project's standing principles number eight. Heading hierarchy is preserved and
three additional `###` entries were appended under Core Principles.

Added sections:
  [SECTION_2_NAME]    → Technology & Security Constraints
  [SECTION_3_NAME]    → Development Workflow & Quality Gates
  [GOVERNANCE_RULES]  → Governance body (amendment, versioning, compliance)

Removed sections: none.

Deferred items / follow-up TODOs: none. No placeholder tokens remain.

Scheduled amendment (not a TODO, a known future event): Principle IV is
time-limited by design and expires when the first real user data is entered,
expected at the end of Phase 3. Replacing it will be a MAJOR bump. See
Governance → Scheduled Amendments.
-->

# SME Cybersecurity Awareness Platform Constitution

## Core Principles

### I. Routers Are Thin (NON-NEGOTIABLE)

A router MUST do only three things: parse and validate the incoming request, call one service
entry point, and render a template or issue a redirect. Modules under `app/routers/` MUST NOT
import `Session`, `select`, or any table model for the purpose of querying. The dependency
direction is `routers → services → models` and is strictly one-way: a service MUST NOT import a
router.

Rationale: the repository layer was deliberately removed to reduce ceremony, which leaves this
principle as the only barrier preventing query logic from spreading into HTTP handlers. It is
mechanically checkable — a router's import list either contains those symbols or it does not.

### II. Services Are HTTP-Agnostic

Service functions MUST accept plain arguments and return plain data or non-table models.
`Request`, `Response`, cookies, headers, and `HTTPException` MUST NOT appear anywhere in
`app/services/`. Services signal failure by raising domain-level exceptions; routers are
responsible for translating those into status codes and messages.

Rationale: a service that never touches HTTP is directly unit-testable without a test client, and
is reusable from the seed script, from CLI tasks, and from other services.

### III. Authorisation Lives in the Service Layer (NON-NEGOTIABLE)

Every service function that reads or mutates module-scoped data MUST take the acting user as an
explicit argument and MUST verify that user's relationship to the module before acting. Hiding a
control in a template is presentation, never enforcement. A trainee MUST NOT be able to reach
another trainee's data by any path, including a direct URL with a guessed identifier.

Rationale: authorisation checked at the only layer that every caller must pass through is the
only authorisation that holds when a second caller (an API, a background job) appears later.

### IV. The Models Are the Schema (TIME-LIMITED)

`SQLModel.metadata.create_all()` at application startup is the single schema authority. No
migration tool is adopted while the system holds no production data. A model change MUST be
applied by recreating the database (`docker compose down -v && docker compose up`) and re-running
the seed script. Live tables MUST NOT be hand-edited to match a changed model.

Rationale: `create_all()` only creates missing tables — it never alters an existing one, so a new
field on an existing model silently does nothing and the application then fails at runtime against
a stale schema. Recreating is free precisely because there is no data to lose, and that condition
is what this principle depends on. It therefore carries an expiry: see Governance → Scheduled
Amendments.

### V. Every Phase Ships Running Software

No phase may be defined as infrastructure-only — there is no "the database phase" and no "the auth
phase". Every phase MUST end with `docker compose up` bringing all three tiers to a state in which
a real user can log in and complete the capability that phase promised.

Rationale: phases that deliver only scaffolding hide integration failures until the end, which is
the most expensive point at which to find them.

### VI. Tests Accompany the Feature

Service-layer tests MUST be written in the same change as the service they cover, not scheduled
afterwards. Tests MUST execute against a disposable MySQL container. SQLite MUST NOT be
substituted for the test database. Router tests are required wherever behaviour is non-obvious.

Rationale: SQLite diverges from MySQL on foreign key enforcement, `VARCHAR` length limits, `JSON`
typing, and string collation — which is precisely the set of guarantees this project relies on
MySQL to provide. A test suite that passes on SQLite would assert nothing about those guarantees.

### VII. Non-Goals Are Defended

The non-goals recorded in the project specification are binding, not advisory. Introducing work
outside the current phase's declared scope MUST be accompanied by explicitly removing something
else from that phase or deferring the new work to a named later phase, and the trade MUST be
recorded in the phase spec.

Rationale: scope creep toward a full Canvas clone is the failure mode most likely to end this
project unfinished. Requiring an explicit trade makes the cost visible at the moment it is
incurred.

### VIII. Simplicity Is a Requirement

Every additional layer, container, dependency, or abstraction MUST justify itself against a
problem that exists now, not one that is anticipated. Where two designs both satisfy the
requirement, the design with fewer moving parts wins — unless the simpler design weakens a
guarantee named elsewhere in this constitution, as substituting SQLite would weaken Principle VI.

Rationale: at this system's size, complexity is the dominant source of defects, and it compounds.
The stated exception exists so that "simpler" is never used to argue away a correctness guarantee.

## Technology & Security Constraints

**Topology**

- The system is three tiers in Docker Compose: `nginx`, `backend`, `db`.
- Only `nginx` publishes a port. `backend` and `db` MUST remain unreachable from the host.
- `backend` MUST NOT query the database before MySQL reports healthy. A Compose healthcheck with
  `condition: service_healthy` is required, and connection retry in application code alongside it.
- MySQL data MUST live on a named Docker volume. A bind mount into the synced project directory
  MUST NOT be used for database storage.

**Database**

- MySQL 8 with InnoDB. `utf8mb4` MUST be set on the server, the database, and the connection URL.
- All timestamps MUST be stored as naive UTC `DATETIME`. Conversion to local time happens only in
  the presentation layer.
- No feature may depend on querying inside a `JSON` column; MySQL cannot index into one.

**Application**

- The frontend is server-rendered Jinja2 with HTMX and Bootstrap 5. A separate JavaScript
  single-page application MUST NOT be introduced.
- A `table=True` SQLModel class MUST NOT be returned from an endpoint or passed into a template.
  Non-table read models are required at every boundary, because table models carry `password_hash`.
- Input MUST be validated through non-table models; SQLModel does not validate table classes.

**Security**

- Passwords are hashed with Argon2 or bcrypt. No other algorithm is permitted.
- Authentication uses server-side sessions stored in MySQL. JWT MUST NOT be introduced. Redis MUST
  NOT be added for sessions or caching without a measured bottleneck justifying the fourth tier.
- Every login MUST require a second factor: a six-digit one-time code emailed to the account
  address, valid for a fixed period and usable once.
- One-time codes MUST be stored hashed rather than in plain text.
- Session cookies MUST be `HttpOnly`, `Secure`, and `SameSite=Lax`. Login MUST be rate-limited.
- CSRF protection is required on every state-changing form post.
- Secrets are supplied through the environment via `pydantic-settings` from a git-ignored `.env`.
  Credentials MUST NOT appear in compose files or be baked into images.

**Email**

- Outbound mail is sent directly from `backend` over SMTP in a worker thread under a hard timeout:
  inline within the request for login codes, and from the in-process scheduler for notifications.
  A message broker, a worker container, or a separate cron container MUST NOT be introduced to
  carry it (Principle VIII).
- SMTP authentication MUST use a Google App Password supplied through the environment. An account
  password MUST NOT be used, and no mail credential may be baked into an image.
- `email_service` MUST NOT import HTTP objects (Principle II) and MUST raise a domain exception on
  delivery failure. A failed send MUST surface to the user as a retryable error; it MUST NOT be
  swallowed into an apparent success.
- `smtp.gmail.com:587` is the only outbound network dependency in the system and it sits on the
  login path. Login fails closed when it is unreachable, and with neither a resend route nor a
  server-side bypass, nobody can sign in until mail is restored. Outbound reachability MUST be
  verified as part of deployment rather than discovered on first use.
- The mail path carries login codes and the notification triggers named in the specification, and
  nothing else. Adding a further outbound message class is a scope change governed by Principle VII.

**Scheduling and notifications**

- Scheduled work runs in-process inside `backend`, started from the FastAPI lifespan. This assumes
  exactly one `backend` replica; running a second one REQUIRES revisiting the scheduler first.
- Every notification MUST exist as a stored row before any email is sent. Email is a delivery
  attempt recorded on the rows it covered, and MUST NOT be a substitute for them, so the two
  channels can never disagree about what a user was told.
- One email MAY cover several rows. Where it does, it MUST stamp every row it included, and the
  in-app list MUST still hold one row per underlying event — grouping is a delivery concern and
  MUST NOT reduce what the user can see or act on individually.
- The scheduled job MUST be idempotent. Running it twice MUST produce neither a second row nor a
  second email: uniqueness constraints prevent the rows, and sending only unstamped rows prevents
  the mail. Neither may rely on the job's own bookkeeping of when it last ran.
- A user MUST be able to read only their own notifications, enforced in the service layer
  (Principle III).

**Resilience**

- A quiz attempt MUST survive a browser crash, tab close, connection loss, or a phone locking.
- Answers MUST persist to the server as the trainee progresses, not only on final submission.
- Time limits are governed by the server clock. The client clock is display only.

## Development Workflow & Quality Gates

**Cycle**

Each phase is one Spec Kit cycle: specify → plan → tasks → build → deploy. A phase does not begin
until the preceding phase has met its definition of done in full.

**Definition of done — every phase, without exception**

1. `docker compose up` on a clean checkout brings all three tiers to a working state.
2. The automated test suite passes against a MySQL container.
3. Layout is verified at all three widths: below 576px (phone), 576–992px (tablet), and above
   992px (desktop). Responsive behaviour is a gate, not a polish pass deferred to the end.
4. No module under `app/routers/` imports `Session` or `select`.
5. No endpoint or template receives a `table=True` model instance.
6. Every new module-scoped service function performs its own authorisation check.

**Review**

Code review MUST verify compliance with the six gates above and with the Core Principles. A change
that violates a principle is rejected or the principle is amended first — it is never waived
silently for convenience.

## Governance

This constitution supersedes ad-hoc practice and prior habit. `lms-project-spec.md` is the runtime
guidance document for design detail and phase content, and MUST remain consistent with this file;
where the two conflict, this constitution governs and the specification is corrected to match.

**Amendment procedure**

An amendment is proposed as an edit to this file accompanied by a Sync Impact Report at its head,
a version bump, and a written rationale. Amendments take effect once merged. Dependent templates
and commands read this file at runtime and are not edited as part of an amendment.

**Versioning policy**

Semantic versioning applies to governance, not to the software:

- MAJOR — a principle is removed, or redefined in a way that invalidates work performed under it.
- MINOR — a principle or section is added, or existing guidance is materially expanded.
- PATCH — clarification, wording, or typo correction that does not change meaning.

**Compliance review**

Compliance is reviewed at the close of every phase, against the definition of done above. Any
complexity introduced during the phase MUST be justified against Principle VIII at that review, or
removed.

**Scheduled amendments**

Principle IV is time-limited by design. It is void from the moment the first real user data is
entered into a running instance, expected at the end of Phase 3. At that point this constitution
MUST be amended — a MAJOR bump — to replace it with an explicit schema-change policy: either
Alembic, or hand-written `ALTER TABLE` scripts kept as the schema record.

There is no backup requirement, because there is no backup. A schema change against an instance
holding real data risks that data with nothing to fall back on. This is the owner's decision.

**Version**: 4.0.0 | **Ratified**: 2026-09-09 | **Last Amended**: 2026-09-09
