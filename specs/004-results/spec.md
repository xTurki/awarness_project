# Feature Specification: Results — Where Everyone Stands

**Feature Branch**: `004-results`

**Created**: 2026-09-10

**Status**: Draft

**Input**: User description: "phase 3"

## Overview

Phase 3 of the SME Cybersecurity Awareness Training Platform. The platform can now assign training and score it. This phase answers the question that follows: **where do I stand?**

One page, listing every module a person is on, what they scored, whether they passed, and what — if anything — is outstanding.

It is the smallest phase in the project and it **adds nothing to the data**. Every number it shows already exists from Phases 1 and 2. This phase is about presenting it.

**It replaces the gradebook** that earlier drafts carried. There are no grade columns, no weightings, no calculated final mark, and no manual grade entry. Everything is scored by machine and nothing concludes, so there is nothing to weight and no final mark to publish.

## Clarifications

### Session 2026-09-10

- Q: Should a trainee's dashboard and their results page be the same page, or two separate pages? → A: The same page — a trainee's dashboard is their results page

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See where you stand (Priority: P1)

A trainee signs in and opens one page. It lists every module they are registered on, and against each: their score, whether they passed, and whether anything is outstanding. Nothing they are not registered on appears, and nothing belonging to anyone else.

**Why this priority**: It is the whole phase. A person who has been assigned five modules currently has no way to see which ones they still owe.

**Independent Test**: Register a trainee on four modules — one never attempted, one in progress, one passed, one failed — and confirm the page shows the right state against each.

**Acceptance Scenarios**:

1. **Given** a trainee registered on several modules, **When** they open their results, **Then** every module they are registered on is listed and no others.
2. **Given** a module whose test the trainee has never attempted, **When** the results are shown, **Then** it reads "not started" rather than being blank or absent.
3. **Given** a module whose test the trainee passed, **When** the results are shown, **Then** it shows the score and reads "passed".
4. **Given** a module whose test the trainee failed, **When** the results are shown, **Then** it shows the score and reads "failed".
5. **Given** a module with no published test at all, **When** the results are shown, **Then** it is listed as having nothing to complete rather than as "not started".
6. **Given** a trainee who scored 40, then 90, then 70 on the same test, **When** their results are shown, **Then** the score shown is 70 — the most recent — consistent with how a person's result is decided everywhere else.
7. **Given** a trainee, **When** they request another person's results directly, **Then** they are refused.
8. **Given** a trainee on a phone, **When** they open their results, **Then** the page is readable without sideways scrolling.

---

### User Story 2 - Look back at one module (Priority: P2)

From the results page a trainee opens a single module and sees every attempt they have made at its test — when, what they scored, and whether each passed — and can open any of them to see the questions and answers.

**Why this priority**: Someone who failed needs to know what they got wrong, and someone retaking a module a year later benefits from seeing what they did last time. The attempt review itself was built in Phase 2; this connects it to something a person can find.

**Independent Test**: Take a test three times, open the module's history from the results page, and confirm all three attempts appear in order with the right scores, each opening to its own review.

**Acceptance Scenarios**:

1. **Given** a trainee with several attempts at a module's test, **When** they open that module from their results, **Then** every attempt is listed with its date, score, and outcome.
2. **Given** a listed attempt, **When** the trainee opens it, **Then** they see the review built in Phase 2, showing their answers and the correct ones.
3. **Given** a trainee with exactly one attempt, **When** they open the module, **Then** that single attempt is shown without the page implying others are missing.
4. **Given** a trainee with no attempts, **When** they open the module, **Then** they are told there is nothing yet and offered the test if one is available to them.

---

### User Story 3 - Pick up something unfinished (Priority: P3)

A trainee started a test, was interrupted, and never came back. Their results page shows that module as in progress, and takes them straight back into the attempt.

**Why this priority**: Phase 2 made an interrupted attempt survivable. Without this, surviving it is not much use, because the trainee has no obvious way to find it again.

**Independent Test**: Start an attempt, leave it, open the results page, and confirm the module reads as in progress and leads back into the same attempt with answers intact.

**Acceptance Scenarios**:

1. **Given** a trainee with an attempt in progress, **When** they open their results, **Then** that module reads as in progress rather than as not started.
2. **Given** a module in progress, **When** the trainee follows it, **Then** they return to the same attempt with the answers they had already given.
3. **Given** an attempt whose time ran out while they were away, **When** they open their results, **Then** it reads as passed or failed on what was answered, not as still in progress.

---

### User Story 4 - See how your people are doing (Priority: P2)

An instructor opens a module they run and sees everyone registered on it, with each person's state and score against it. Anyone who has not passed is at the top, and any of them can be opened to see what they actually answered.

**Why this priority**: Training nobody is checking is not training. Until now the platform has collected every fact needed to answer "who still owes this?" and shown it to nobody who could act on it.

**Independent Test**: As an instructor, open a module with five registered people in different states, and confirm each state is right and that a module you do not run is refused.

**Acceptance Scenarios**:

1. **Given** an instructor on a module they are assigned to, **When** they open its results, **Then** every person registered on it is listed with their state and score.
2. **Given** a mixed group, **When** the list is shown, **Then** those who have not passed appear before those who have.
3. **Given** a listed person, **When** the instructor opens them, **Then** they see that person's attempts at this module's test and can open any one of them.
4. **Given** an instructor, **When** they request the results of a module they are not assigned to, **Then** they are refused.
5. **Given** an instructor, **When** they look for a view covering more than one module, **Then** none is offered.
6. **Given** an instructor on a phone, **When** they open a module's results, **Then** the list is readable without sideways scrolling.
7. **Given** a module where thirty people have passed, **When** the instructor publishes a replacement test, **Then** they are warned beforehand that all thirty will revert to "not started".

---

### Edge Cases

- **Registered on a module with no published test.** Listed as having nothing to complete. It is not a failure and not an omission.
- **The test was replaced after being attempted.** Everyone reverts to "not started" for that module, because state follows the currently published test. Their old attempts stay in their history. Publishing a replacement therefore resets the whole cohort — see the note in Assumptions.
- **A registration is removed.** The module leaves the person's results immediately. Their attempts are not deleted, but they are no longer theirs to see.
- **An instructor corrected a score by hand.** The results page shows the corrected score, because that is now the attempt's score.
- **A test is unpublished after someone passed it.** Their result stands. Unpublishing stops new attempts; it does not erase old ones.
- **Someone is registered on a module as an instructor.** Their own results page concerns what they must complete, not what they teach. A module they instruct does not appear as training they owe.
- **An instructor who is also a trainee on the module.** They appear in their own roster like anyone else, and the module also shows in their personal results.
- **A very long list.** Someone registered on thirty modules gets a page that stays readable, ordered so that anything outstanding is easiest to find.
- **No registrations at all.** The page says so plainly rather than showing an empty frame.

## Requirements *(mandatory)*

### Functional Requirements

**What a person sees**

- **FR-001**: System MUST list, on a trainee's dashboard, each module they hold a registration on and no module they do not. This dashboard **is** the results page — there is no second, separate list of the same modules. Instructor and administrator dashboards are unaffected.
- **FR-002**: System MUST show, against each listed module, the person's current state in it.
- **FR-003**: System MUST distinguish these states: no test available · not started · in progress · passed · failed.
- **FR-004**: System MUST show the score alongside any state where one exists.
- **FR-005**: System MUST decide the state and the score from the person's most recent submitted attempt, consistent with how a result is decided elsewhere in the platform.
- **FR-006**: System MUST show a module carrying no published test as having nothing to complete, distinct from a test not yet started.
- **FR-007**: System MUST order the list so that outstanding items are found first.
- **FR-008**: System MUST decide a person's state from their attempts at the module's **currently published** test only. Attempts at a test that has since been replaced MUST NOT count towards their state, though they remain visible in that person's history.

**Looking into one module**

- **FR-009**: System MUST let a person open any module from their results and see every attempt they have made at its test, with the date, score, and outcome of each.
- **FR-010**: System MUST let a person open any of their own attempts and reach the review of it.
- **FR-011**: System MUST lead a person with an attempt in progress back into that attempt, with the answers already given intact.
- **FR-012**: System MUST show a module with no attempts as such, and offer its test where one is available to that person.

**Who may see what**

- **FR-013**: System MUST refuse any person access to another person's results, history, or attempts.
- **FR-014**: System MUST stop showing a module in a person's results as soon as their registration on it is removed.
- **FR-015**: System MUST exclude from a person's own results any module they hold only as an instructor, since it is not training they owe.
- **FR-016**: System MUST let an instructor see, for each module they are assigned to, every person registered on it with that person's state and score.
- **FR-017**: System MUST offer the same five states on the instructor's view as on a person's own, decided the same way.
- **FR-018**: System MUST let an instructor open any listed person's attempt history for that module, and from there any individual attempt.
- **FR-019**: System MUST refuse an instructor the roster or results of any module they are not assigned to.
- **FR-020**: System MUST order the instructor's list so that people who have not passed are found first.
- **FR-021**: System MUST NOT provide any view spanning more than one module. There is no organisation-wide picture in this phase.

**Presentation**

- **FR-022**: System MUST present the results page and module history usably at phone, tablet, and desktop widths, with no sideways scrolling of the page itself.
- **FR-023**: System MUST make each state legible without relying on colour alone.
- **FR-024**: System MUST show a person with no registrations a clear statement to that effect rather than an empty page.

**Boundaries**

- **FR-025**: System MUST derive everything on these pages from registrations and attempts already recorded. It MUST NOT introduce any new record of a result.
- **FR-026**: System MUST NOT provide any way to enter, adjust, or weight a score on these pages. Correcting a score remains an instructor action on the attempt itself.
- **FR-027**: System MUST warn an instructor, before they publish a test into a module that already has one, that everyone registered on that module will revert to "not started" and how many people that is. The warning applies to the publish action introduced in Phase 2; this phase defines what makes it necessary.

### Key Entities

This phase introduces no new entity. Everything it shows is derived from what already exists:

- **Registration** (from Phase 1) — decides which modules appear for a person.
- **Test** (from Phase 2) — decides whether a module has anything to complete, and what the pass mark is.
- **Attempt** (from Phase 2) — supplies the score, the outcome, and the history. The most recent submitted one decides the state shown.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A trainee registered on modules can tell which ones they still owe within ten seconds of opening their results.
- **SC-002**: Every module a person is registered on appears in their results, and no other, in 100% of cases.
- **SC-003**: The state shown for each module matches the person's most recent submitted attempt in 100% of cases.
- **SC-004**: A module with no published test is never shown as "not started", in 100% of cases.
- **SC-005**: A person can reach another person's results, history, or attempts in 0% of attempts.
- **SC-006**: A removed registration disappears from that person's results on their next page load, in 100% of cases.
- **SC-007**: An interrupted attempt is reachable from the results page and resumes with its answers intact, in 100% of cases.
- **SC-008**: The results page is readable at 360 pixels wide with no sideways page scrolling, including for a person registered on thirty modules.
- **SC-009**: Every state is distinguishable without colour, verified by viewing the page in greyscale.
- **SC-010**: This phase adds no stored record of a result; every figure shown is reproducible from registrations and attempts alone.
- **SC-011**: An instructor can identify everyone on their module who has not yet passed within ten seconds of opening it.
- **SC-012**: An instructor can reach the results of a module they are not assigned to in 0% of attempts.
- **SC-013**: No view anywhere in this phase spans more than one module.
- **SC-014**: An instructor publishing a replacement test is told, before confirming, exactly how many people it will reset, in 100% of cases.
- **SC-015**: Every user-facing behaviour above is covered by an automated test that fails if the behaviour regresses.

## Assumptions

**Chosen defaults**, adopted because the phase description did not fix them and a reasonable default exists:

- **"Due" and "overdue" are not states in this phase.** They depend on a retake interval, which arrives in Phase 4. This phase settles the vocabulary and delivers the five states it can actually compute; Phase 4 adds the two that need a schedule behind them.
- An in-progress attempt is a state worth showing. Phase 2 went to some trouble to make an interrupted attempt survivable, and a person who cannot find it again gains nothing from that.
- Outstanding items sort above completed ones. Within outstanding, order by when the person was registered, oldest first.
- A person registered on a module as its instructor does not see it among their own training. If they are also registered on it as a trainee, they do.
- A score is shown as a percentage, matching how it is expressed everywhere else.
- **A trainee's dashboard is their results page.** One route, one template, one list. The plain module list Phase 1 described for trainees is replaced by this one rather than sitting alongside it. Instructors and administrators keep their own dashboards, which show different things.
- An instructor's view covers one module at a time. Nothing aggregates across modules, for anyone.

> **A consequence of deciding state from the currently published test.** Replacing a test resets everyone registered on that module to "not started" — including people who passed the previous version yesterday. Correcting a single misspelled question therefore invalidates the whole group's training record, and once Phase 4 exists it will make all of them due at once and send them all a notification.
>
> This is the honest reading of "the module now asks something different", and it puts real weight behind getting a test right before publishing it. But an instructor needs to know it before they click, which is what FR-027 requires.

**Dependencies**:

- Phase 1 for modules and registrations, Phase 2 for tests and attempts. This phase reads both and writes neither.
- Phase 4 depends on the state vocabulary settled here; its notifications describe a person as due or overdue against the same five states.

**Deliberately excluded**, so that their absence is a decision rather than an oversight:

- Any gradebook: no grade columns, no weightings, no calculated final mark, no manual grade entry.
- Any certificate, printable record, or proof of completion.
- Exporting results to a file.
- Any view spanning more than one module, including an organisation-wide picture for an administrator. Nobody can currently answer "how many of our staff have completed their training?" in one place.
- Charts, trends, or comparisons between people.
- Any new stored record of a result. Everything is derived, so nothing can drift out of step with the attempts it came from.
