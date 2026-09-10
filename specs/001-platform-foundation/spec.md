# Feature Specification: Platform Foundation — Identity, Access & Shell

**Feature Branch**: `001-platform-foundation`

**Created**: 2026-09-10

**Status**: Draft

**Input**: User description: "phase 0"

## Overview

Phase 0 of the SME Cybersecurity Awareness Training Platform. It establishes who people are, how they prove it, what they may reach once they have, and a running environment to put it all in.

It deliberately contains no training modules, no content, and no quizzes. Those begin in Phase 1. What it delivers is an installation an administrator can sign into, put real people into, and hand out access from — the smallest thing that is genuinely useful, and the foundation every later phase assumes.

## Clarifications

### Session 2026-09-10

- Q: What language should the interface be in, and does it need to read right-to-left? → A: English only, left-to-right
- Q: How is the platform's data backed up? → A: It is not
- Q: What does the platform log? → A: Nothing beyond what the server prints by default

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sign in with a second factor (Priority: P1)

A person opens the platform, enters their email address and password, and is told to check their email. A six-digit code has been sent to them. They enter it and arrive at their dashboard, signed in.

This happens on every sign-in, for everyone, with no "remember this device" exemption.

The very first time someone signs in on an account an administrator set up for them, they are asked to choose their own password before going any further. The administrator knows the password they issued; this is how the person takes sole possession of the account.

**Why this priority**: Nothing else in the platform is reachable without it. It is the smallest slice that produces something a real person can use, and every subsequent phase assumes it works.

**Independent Test**: Fully testable with a seeded account and a mailbox. Sign in, receive a code, enter it, land on a dashboard. Delivers the entire value of the phase on its own.

**Acceptance Scenarios**:

1. **Given** a person with a valid email and password, **When** they submit them, **Then** a six-digit code is sent to that address and they are taken to a page asking for it.
2. **Given** a code has just been sent, **When** the person enters it correctly, **Then** they are signed in and see their dashboard.
3. **Given** a code has been sent, **When** the person enters the wrong code, **Then** they are told it is incorrect and remain on the same page, still able to try again.
4. **Given** a code was sent more than ten minutes ago, **When** the person enters it, **Then** it is refused as expired and they are told to sign in again.
5. **Given** a code has already been used successfully, **When** anyone submits it again, **Then** it is refused.
6. **Given** a person is midway through entering their code, **When** they start a fresh sign-in instead, **Then** a new code is issued and the previous one stops working.
7. **Given** an account whose password was set by an administrator, **When** the person completes sign-in for the first time, **Then** they are asked to choose a new password before they can reach anything else.
8. **Given** a person being asked to choose a new password, **When** they try to reach any other page instead, **Then** they are returned to that request until a new password is set.
9. **Given** a person has chosen a new password, **When** they sign in again later, **Then** they are not asked to change it again.

---

### User Story 2 - See a workspace that matches your role (Priority: P2)

Once signed in, a person sees a dashboard and navigation appropriate to what they are: an administrator, an instructor, or a trainee. The three do not see the same thing.

**Why this priority**: Without it, sign-in delivers a blank page. It is also where the platform's look and feel is established, and getting that right early is far cheaper than retrofitting it around finished features.

**Independent Test**: Sign in as each of the three seeded roles and confirm each sees navigation and a dashboard appropriate to them, and cannot reach areas belonging to another role.

**Acceptance Scenarios**:

1. **Given** a signed-in administrator, **When** they view their dashboard, **Then** they see navigation for administration that a trainee does not see.
2. **Given** a signed-in trainee, **When** they view their dashboard, **Then** they see a trainee's navigation and no administrative options.
3. **Given** a signed-in trainee, **When** they request an administrator-only address directly, **Then** they are refused, not merely shown a page with the controls hidden.
4. **Given** any signed-in person on a phone, **When** they view any page, **Then** the layout is usable and the page does not scroll sideways.

---

### User Story 3 - End access, immediately (Priority: P2)

A person signs out and their session ends. Separately, when an administrator disables an account, that account loses access straight away rather than at some later point.

**Why this priority**: Revocation is the entire reason this platform holds sessions on the server rather than in a token. If disabling an account does not take effect immediately, the choice was pointless.

**Independent Test**: Sign in, sign out, confirm protected pages are no longer reachable. Separately, disable an account while it is signed in and confirm the next page request is refused.

**Acceptance Scenarios**:

1. **Given** a signed-in person, **When** they sign out, **Then** their session ends and protected pages are no longer reachable with it.
2. **Given** a person whose account is disabled while they are signed in, **When** they next request any protected page, **Then** they are refused and returned to sign-in.
3. **Given** a session older than its permitted lifetime, **When** it is used, **Then** it is refused and sign-in is required again.

---

### User Story 4 - Administer accounts (Priority: P2)

An administrator sees everyone who has an account, creates accounts, corrects a name or address, resets a forgotten password, promotes someone to instructor, and switches off the account of someone who has left.

**Why this priority**: There is no other way an account can come into existence. Nobody registers themselves, so without this the platform holds only the accounts seeded at installation and cannot take on a single real person. It is also the only route back for a forgotten password, since self-service reset is out of scope — an administrator who is unreachable means a locked-out person stays locked out.

**Independent Test**: As an administrator, create an account, sign in as it, then edit it, change its role to instructor, reset its password, and deactivate it — confirming after each step that the change took effect for that account.

**Acceptance Scenarios**:

1. **Given** an administrator, **When** they view account administration, **Then** they see every account with its email, name, role, and whether it is active.
2. **Given** an administrator, **When** they create an account with a chosen role and an initial password, **Then** that account exists, is active, and can sign in.
3. **Given** an administrator, **When** they create an account using an email address that already has one, **Then** it is refused and no second account is created.
4. **Given** a signed-out visitor, **When** they look for a way to create an account for themselves, **Then** none is offered anywhere in the platform.
5. **Given** an administrator, **When** they change an account's role, **Then** that account's navigation and permitted areas change accordingly on its next request.
6. **Given** an administrator, **When** they reset an account's password, **Then** the previous password no longer works and the new one does.
7. **Given** an administrator has reset someone's password, **When** that person next signs in, **Then** they are required to choose a new password before continuing, exactly as on a new account.
8. **Given** an administrator, **When** they deactivate an account, **Then** that account is refused access immediately, including any session already open.
9. **Given** an instructor or a trainee, **When** they request account administration, **Then** they are refused.

---

### User Story 5 - Bring the platform up from nothing (Priority: P3)

Someone setting the platform up on a fresh machine issues a single command and, a few minutes later, has a working sign-in page and a set of demonstration accounts to sign in with.

**Why this priority**: It is what makes every other story demonstrable, and what makes the phase deliverable rather than a local-machine curiosity. Lower than P1 and P2 only because it delivers no value to an end user directly.

**Independent Test**: On a machine that has never run the platform, follow the documented setup and confirm a working sign-in page and usable demonstration accounts.

**Acceptance Scenarios**:

1. **Given** a machine with no prior installation, **When** the documented setup command is run, **Then** the platform becomes reachable and presents a sign-in page.
2. **Given** a fresh installation, **When** the seeding step is run, **Then** one administrator, one instructor, and five trainee accounts exist and can sign in.
3. **Given** the data store takes time to become ready, **When** the platform starts, **Then** it waits for readiness rather than failing, and becomes available without manual intervention.
4. **Given** a running installation, **When** anyone attempts to reach the data store or the application directly from outside, **Then** they cannot; only the public entry point is reachable.
5. **Given** a restart of the whole installation, **When** it comes back up, **Then** every account created before it is still there.

---

### User Story 6 - Be told clearly when email fails (Priority: P4)

Email delivery fails — an outage, a blocked connection, an expired credential. The person trying to sign in is told plainly and quickly, rather than being left on a page waiting for a code that will never arrive.

**Why this priority**: It changes nothing when things work. It matters because every sign-in needs an emailed code, so a mail outage locks everybody out and the least the platform can do is say so.

**Independent Test**: Disable outbound mail and confirm the sign-in attempt fails within seconds with a message that explains what happened.

**Acceptance Scenarios**:

1. **Given** outbound email is failing, **When** someone attempts to sign in, **Then** they are told plainly that the code could not be sent and that signing in again is how to retry, rather than being left waiting for a code that will never arrive.
2. **Given** email delivery is slow, **When** sign-in is attempted, **Then** the attempt fails within a bounded time with a clear message rather than hanging.

---

### Edge Cases

- **Abandoning the password change.** Someone closes the browser at the choose-a-password step. Their next sign-in returns them to it; there is no way past it and no partial state left behind.
- **An administrator resets a password for someone already signed in.** That person's existing session continues until it ends normally, but their next sign-in requires a new password.
- **Two sign-ins at once.** A person starts signing in on their laptop, then again on their phone. The second issues a new code; the first stops working. The person is not told why the older code failed beyond "incorrect".
- **Repeated wrong codes.** Nothing throttles this. The code expires after ten minutes and a fresh sign-in replaces it, and those are the only limits. See the note under Assumptions.
- **Repeated sign-in attempts.** Someone submits many password attempts against one address. Attempts are throttled.
- **Phone locks during code entry.** The person unlocks and returns; the page is still there and the code still works, provided it has not expired.
- **Code arrives after expiry.** Mail was delayed past the code's lifetime. The person is told it has expired and can simply sign in again.
- **Session expires mid-use.** The next action returns the person to sign-in rather than failing obscurely.
- **Data store unavailable at startup.** The platform waits and retries rather than starting in a broken state.
- **Data store unavailable while running.** People see an error page, not a blank response or a stack trace.

## Requirements *(mandatory)*

### Functional Requirements

**Identity and accounts**

- **FR-001**: System MUST hold accounts, each with an email address unique across the platform, a name, and exactly one of three roles: administrator, instructor, or trainee.
- **FR-002**: System MUST store passwords only in a form from which the original cannot be recovered, using a deliberately slow hashing method.
- **FR-003**: System MUST allow an account to be marked inactive, and MUST refuse both sign-in and continued access to an inactive account.
- **FR-004**: System MUST provide a way to create a starting set of accounts — one administrator, one instructor, and five trainees — for a newly installed platform.
- **FR-005**: System MUST enforce and state a minimum password standard wherever a password is set.
- **FR-006**: System MUST provide no way for a visitor to create an account. Accounts come only from an administrator or from the starting set.
- **FR-007**: System MUST let an administrator see every account with its email address, name, role, and active state.
- **FR-008**: System MUST let an administrator create an account with any role, edit an account's name and email address, reset its password, change its role, and deactivate or reactivate it.
- **FR-009**: System MUST restrict every account-administration capability to administrators, refused at the point of request for anyone else.
- **FR-010**: System MUST mark an account as requiring a new password whenever an administrator creates it or resets its password.
- **FR-011**: System MUST, once such an account has completed sign-in, require a new password to be chosen before any other part of the platform can be reached, and MUST clear the requirement once one is set.
- **FR-012**: System MUST refuse a proposed new password that fails the standard in FR-005.

**Signing in**

- **FR-013**: System MUST require two steps for every sign-in by every role: correct credentials, then a single-use numeric code sent to the account's email address.
- **FR-014**: System MUST NOT provide any way to skip the second step — no trusted device, no remembered browser, no per-account exemption.
- **FR-015**: System MUST store codes in a form from which the original cannot be recovered.
- **FR-016**: System MUST expire a code after a fixed period and MUST refuse it thereafter.
- **FR-017**: System MUST refuse a code that has already been used successfully.
- **FR-018**: System MUST invalidate any outstanding code when a fresh sign-in is started for the same account.
- **FR-019**: System MUST limit how frequently sign-in attempts may be made from the same source.
- **FR-020**: System MUST tell a person plainly when a code could not be sent, and MUST make clear that signing in again is how to retry.
- **FR-021**: System MUST fail a code-sending attempt within a bounded time rather than leaving the person waiting indefinitely.

**Staying signed in, and stopping**

- **FR-022**: System MUST keep sign-in state on the server, such that access can be withdrawn at any time without waiting for anything to expire.
- **FR-023**: System MUST end a person's access when they sign out.
- **FR-024**: System MUST expire sign-in state after a fixed period and require signing in again.
- **FR-025**: System MUST protect every action that changes state against being triggered from another site.

**What people see**

- **FR-026**: System MUST present a dashboard and navigation determined by the signed-in person's role, with the three roles seeing materially different navigation.
- **FR-027**: System MUST refuse access to areas outside a person's role at the point of request, not merely hide the controls that lead there.
- **FR-028**: System MUST present every page usably at phone, tablet, and desktop widths, with no sideways scrolling of the page itself.
- **FR-029**: System MUST let a phone offer a received code for entry automatically.

**Running the platform**

- **FR-030**: System MUST be startable on a clean machine with a single documented command, reaching a working sign-in page without further manual steps.
- **FR-031**: System MUST expose only its public entry point; the application and the data store MUST NOT be reachable from outside.
- **FR-032**: System MUST wait for its data store to become ready at startup rather than failing.
- **FR-033**: System MUST take all secrets from its environment, and MUST NOT carry any credential inside its published artefacts or configuration files held in version control.
- **FR-034**: System MUST preserve its data across restarts.
- **FR-035**: System MUST be kept under version control from this phase onward, in a **local repository**. There is no remote and no shared hosting — the owner's decision. Already satisfied: the repository was initialised before this phase began.
- **FR-036**: Automated tests MUST be runnable on demand by any team member with a single documented command. Running them automatically on every change is deferred to a later phase.

### Key Entities

- **User**: A person who can sign in — the table is `user`, and the screens that manage them are called account administration. Holds their email address, name, role, whether they are active, and their password in unrecoverable form. Records whether the person must choose a new password before continuing, which is set whenever an administrator creates the account or resets its password and cleared once they do. Also carries whatever is outstanding for a sign-in currently in progress — the pending code in unrecoverable form and the moment it stops being valid — both cleared once used.
- **Session**: Evidence that a particular account signed in successfully, held by the platform rather than by the browser. Records when it began, when it ceases to be valid, and enough about its origin to be recognised. Removed on sign-out, and removable at any time to withdraw access.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person with valid credentials and access to their mailbox completes sign-in, including receiving and entering the code, in under two minutes.
- **SC-002**: A requested code reaches the recipient's mailbox within sixty seconds in at least 95% of attempts.
- **SC-003**: Sign-in and the dashboard are usable at 360 pixels wide with no sideways page scrolling, and the same is true at tablet and desktop widths.
- **SC-004**: A code that is wrong, expired, or already used is refused in 100% of attempts.
- **SC-005**: A signed-out or expired session grants access to no protected page, in 100% of attempts.
- **SC-006**: A person unfamiliar with the platform brings it from nothing to a working sign-in page, with usable demonstration accounts, in under ten minutes.
- **SC-007**: Neither the data store nor the application is reachable from outside the machine.
- **SC-008**: When email delivery is failing, a person is told so within fifteen seconds of attempting to sign in.
- **SC-009**: An administrator creates a working account, from opening the form to that person signing in, in under three minutes.
- **SC-010**: An account deactivated by an administrator is refused on its very next request, including from a session already open.
- **SC-011**: No route exists, anywhere in the platform, by which a signed-out visitor can create an account.
- **SC-012**: An account whose password was set by an administrator cannot reach any part of the platform beyond the choose-a-password step until a new password is set, in 100% of attempts.
- **SC-013**: Every user-facing behaviour above is covered by an automated test that fails if the behaviour regresses.

## Assumptions

**Chosen defaults**, adopted because the phase description did not fix them and a reasonable default exists:

- A code remains valid for ten minutes. Long enough to survive slow mail, short enough to bound the window.
- A session lasts twelve hours. Chosen against the fact that every sign-in costs an email round trip: a shorter session would make the second factor tiring for someone working a full day, a longer one weakens the point of holding sessions at all.
- Sign-in attempts are limited to a handful per source per short interval. Code entry is deliberately not throttled — see the note below.
- A person choosing their first password is not asked for the administrator's password again. They have just proved who they are with that password and an emailed code; asking a third time adds friction without adding proof.
- The demonstration accounts created at installation are exempt from the first-sign-in password change, so the platform can be shown working without a detour. Real accounts created by an administrator are never exempt.
- Passwords must be at least eight characters. No composition rules.
- "Materially different navigation" between roles means at minimum that administrative navigation is absent for instructors and trainees.
- **The interface is English, left-to-right.** One stylesheet, no direction handling anywhere in the shell that every later phase renders inside.

> **A consequence of not throttling code entry.** A six-digit code is one of a million, and nothing limits how many guesses may be submitted inside its ten-minute life. An attacker who already knows someone's password could therefore work through codes. This was accepted deliberately when the security surface was reduced; it is written here so that its absence is a decision on record rather than something nobody noticed.

**Dependencies and environmental assumptions**:

- An email account and an application-specific credential for it are available for sending, and the machine is permitted to make outbound mail connections. Without this, nobody can sign in.
- Everyone who signs in can reach their own email on a device they can also use to reach the platform.
- The platform runs as a single instance. Nothing here assumes or supports more than one.
- No training content, modules, tests, results, or notifications exist in this phase. Signing in, being administered, and seeing an appropriately shaped but largely empty workspace is the whole of it.
- There is no existing data to preserve. The platform may be destroyed and recreated freely throughout this phase.
- **Nothing is backed up.** The database lives in one Docker volume on one machine. If that machine or volume is lost, the data is gone and cannot be recovered.

**Deliberately excluded**, so that their absence is a decision rather than an oversight:

- Any way for a person to create their own account. Every account is created by an administrator or comes from the starting set.
- Self-service password reset. An administrator resets passwords (FR-008), and the person then chooses their own at their next sign-in. A person who forgets their password and cannot reach an administrator has no route back.
- A record of who did what — no audit trail exists in this platform.
- A route to resend a code without starting sign-in again.
- Any second-factor channel other than email.
- Any backup, snapshot, or export of the database.
- Application logging of any kind — no structured logs, no log files, no aggregation. Whatever the server prints to the console is all there is.
- Arabic, right-to-left layout, or any second interface language.
