# Feature Specification: Scheduling & Notifications

**Feature Branch**: `005-scheduling-notifications`

**Created**: 2026-09-10

**Status**: Draft

**Input**: User description: "phase 4"

## Overview

Phase 4 of the SME Cybersecurity Awareness Training Platform, and the last one planned.

Everything so far waits for someone to open a page. This phase is the first thing the platform does on its own: it works out who is due to retake their training, and tells them — without anybody signed in and without anybody remembering to check.

It also completes the state vocabulary. Phase 3 delivered the five states it could compute; this phase adds the two that need a schedule behind them: **due** and **overdue**.

This is what turns the platform from a place where training happens into something that keeps training current. It is also the only part of the system that acts without a person triggering it, which is why most of its requirements are about not doing that twice.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Set how often training must be repeated (Priority: P1)

An instructor decides their module's test must be retaken every ninety days, or every year, and sets that once. From then on the platform works out who is due and when, for everyone on the module, without the instructor touching it again.

**Why this priority**: Nothing else in the phase has anything to act on until a test recurs. It is also the whole point of the platform for an SME — training that renews itself.

**Independent Test**: Set a module's test to repeat every 90 days, then confirm that a person who last passed 91 days ago shows as overdue and one who passed yesterday does not.

**Acceptance Scenarios**:

1. **Given** an instructor on their own module, **When** they set a retake interval on its test, **Then** it is saved and shown to trainees alongside the test's other terms.
2. **Given** a test with no retake interval, **When** it is saved, **Then** it is treated as a one-off: nobody becomes due for it a second time, though it may still carry a completion period for the first.
3. **Given** an instructor setting a retake interval, **When** the test has no pass mark, **Then** it is refused, because a cycle that restarts on passing needs to know what passing means.
4. **Given** a test with a retake interval, **When** a trainee has used the permitted number of attempts without passing, **Then** they may still attempt it again — attempt limits do not apply to a recurring test.
5. **Given** an instructor changes the retake interval, **When** the change is saved, **Then** every registered person's due date is recalculated from it at once.
6. **Given** an instructor, **When** they set a retake interval on a module they are not assigned to, **Then** they are refused.
7. **Given** a one-off test, **When** the instructor sets a completion period of thirty days, **Then** each registered person becomes due thirty days after their own registration.
8. **Given** a one-off test with a completion period, **When** a person passes it, **Then** they never become due for it again.

---

### User Story 2 - Be told before it lapses, and while it is lapsed (Priority: P1)

A trainee passed the phishing module ten months ago. Two weeks before it lapses they are told. If the date passes without them retaking it, they are reminded weekly until they do.

**Why this priority**: A due date nobody is told about is a spreadsheet, not a platform. This is the reason the phase exists.

**Independent Test**: Set a 90-day interval, arrange a person who passed 76 days ago and one who passed 100 days ago, run the daily process, and confirm the first is warned it is coming and the second is told it has lapsed.

**Acceptance Scenarios**:

1. **Given** a person whose due date is within the warning period, **When** the daily process runs, **Then** they are notified that the module is coming due, once.
2. **Given** a person whose due date has passed, **When** the daily process runs, **Then** they are notified that it is overdue.
3. **Given** a person still overdue a week later, **When** the daily process runs again, **Then** they are reminded again.
4. **Given** a person overdue on three modules, **When** the daily process runs, **Then** they receive **one** message covering all three, not three messages.
5. **Given** the daily process has already run today, **When** it is run a second time, **Then** nobody receives anything again and no duplicate record is created.
6. **Given** a person who retakes and passes, **When** the daily process next runs, **Then** they are not reminded, and their next due date is a full interval away.
7. **Given** a module whose test has neither a retake interval nor a completion period, **When** the daily process runs, **Then** nobody is told anything about it.
8. **Given** a person who passed and then retook the same test and scored below the pass mark, **When** the daily process runs, **Then** they are due immediately, because their most recent attempt did not pass.
9. **Given** an instructor publishes a replacement test on a module where thirty people had passed, **When** the daily process next runs, **Then** all thirty are notified.

---

### User Story 3 - See what you have been told (Priority: P2)

A trainee signs in and sees that they have been notified about something. They open the list, read it, and go straight to what it concerns.

**Why this priority**: Email arrives where the platform cannot see it, and gets filtered, deleted, and missed. A record inside the platform is what makes a notification something a person can come back to.

**Independent Test**: Trigger a notification, sign in as that person, and confirm it appears in their list, is marked as read once seen, and leads to the module it concerns.

**Acceptance Scenarios**:

1. **Given** a person with unread notifications, **When** they sign in, **Then** the application shell shows that something is waiting.
2. **Given** a person opening their notifications, **When** the list is shown, **Then** each entry says what it concerns and when it arrived, newest first.
3. **Given** a notification about a module, **When** the person follows it, **Then** they arrive at that module.
4. **Given** a person who has read their notifications, **When** they sign in again, **Then** nothing is shown as waiting unless something new arrived.
5. **Given** a person overdue on three modules, **When** they open their notifications, **Then** they see **three** entries — one per module — even though they received one email.
6. **Given** a person, **When** they request another person's notifications, **Then** they are refused.

---

### User Story 4 - Be told when something concerns you (Priority: P3)

Someone is registered onto a module, or their test result becomes available. They are told at the moment it happens, not on the next daily run.

**Why this priority**: Useful and cheap — both events happen while a request is being handled, so neither needs the scheduled process. Lowest priority because neither is something a person is waiting for.

**Independent Test**: Register a person onto a module and confirm they are notified; have them submit a test and confirm they are notified of the result.

**Acceptance Scenarios**:

1. **Given** an instructor registers someone onto a module, **When** the registration is made, **Then** that person is notified, immediately and individually.
2. **Given** a trainee submits a test, **When** it is scored, **Then** they are notified of the result, immediately and individually.
3. **Given** several people registered in one action, **When** the registrations are made, **Then** each is notified about their own.

---

### Edge Cases

- **Nobody has ever passed.** A person registered on a recurring module who has never passed it is due from the moment they were registered, and overdue from the day after.
- **Someone passes, then retakes to revise and scores below the pass mark.** They are due immediately and overdue the next day, and will be reminded. The route out is to retake and pass, which the review from Phase 2 makes straightforward.
- **Someone who never passes.** They are reminded weekly, indefinitely. Unlimited retakes mean they always have a way out, so it is never a trap — but it also never stops on its own.
- **A registration is removed while someone is overdue.** They stop being due and stop being reminded. Existing notifications stay in their list.
- **A person is registered onto a module they already passed under a previous test.** Phase 3 resets them to "not started", so they are due immediately.
- **The daily process does not run.** Nothing is lost. The next run finds everyone who became due in the meantime and tells them then.
- **The daily process runs while someone is mid-attempt.** Their attempt is untouched. If they were overdue when it started, they remain overdue until they pass.
- **Email fails while the daily process is running.** The in-app record still exists; only the email is missing. The next run may retry it, because it was never marked as sent.
- **A person with no email that works.** They still see everything in the platform. Email is a second channel, not the record.
- **An instructor sets an interval shorter than the warning period** — say a 7-day retake with a 14-day warning. The warning would fire before the person had even taken it. Refused when saved.
- **A test's pass mark is raised after people passed under the old one.** Phase 2 freezes a test once attempted, so this cannot happen to an existing test — only a replacement can change it, and a replacement resets everyone anyway.

## Requirements *(mandatory)*

### Functional Requirements

**Recurring tests**

- **FR-001**: System MUST let an instructor set, on a test in a module they are assigned to, how often it must be retaken.
- **FR-002**: System MUST treat a test with no retake interval as one-off, meaning nobody becomes due for it a second time. A one-off test may still carry a completion period — see FR-035.
- **FR-003**: System MUST refuse a retake interval on a test that has no pass mark.
- **FR-004**: System MUST refuse a retake interval shorter than the period used to warn people in advance.
- **FR-005**: System MUST NOT apply the permitted number of attempts to a test that recurs; a person may retake it as often as they need until they pass.
- **FR-006**: System MUST show a test's retake interval to the people registered on it.

**Working out who is due**

- **FR-007**: System MUST derive a person's due date for a recurring test rather than storing it, so that changing the interval re-dates everyone at once.
- **FR-008**: System MUST treat a person who has never passed a recurring test as due from the moment they were registered on its module.
- **FR-009**: System MUST run the interval from a person's **most recent attempt, and only if that attempt passed**. Where their most recent attempt did not pass, they are due immediately. This is the same rule Phases 2 and 3 use to decide what represents a person, applied to dates.
- **FR-010**: System MUST add **due** and **overdue** to the states delivered in Phase 3, decided from the due date, and MUST show them everywhere those states are shown.
- **FR-011**: System MUST stop treating a person as due or overdue as soon as they pass, and MUST set their next due date a full interval later.
- **FR-012**: System MUST stop treating a person as due or overdue as soon as their registration on the module is removed.

**Telling people**

- **FR-013**: System MUST notify a person a configurable period before their due date, once.
- **FR-014**: System MUST notify a person once their due date has passed, and repeat at a configurable interval until they pass.
- **FR-015**: System MUST notify a person when they are registered onto a module, at the moment it happens.
- **FR-016**: System MUST notify a person when their test result becomes available, at the moment it happens.
- **FR-017**: System MUST create a separate notification record for each module a notification concerns.
- **FR-018**: System MUST send registration and result notifications individually and immediately.
- **FR-019**: System MUST combine all of one person's due and overdue notifications from a single run into **one** message to them.
- **FR-020**: System MUST notify everyone made due by a replacement test on the next run, with no grace period and no suppression. The instructor was warned before publishing what it would do.

**Not telling people twice**

- **FR-021**: System MUST create a notification record before any message is sent, and MUST treat that record as the notification. A message is a delivery of it, never a substitute for it.
- **FR-022**: System MUST NOT create a second notification record for the same person, the same kind of event, the same module, and the same due date.
- **FR-023**: System MUST send only notifications not already sent, and MUST mark each as sent once it has been.
- **FR-024**: System MUST produce no duplicate record and no second message when the scheduled process runs more than once for the same day.
- **FR-025**: System MUST leave a notification unmarked when its message could not be delivered, so that a later run may try again.

**Running unattended**

- **FR-026**: System MUST run the process that finds who is due once a day, without anyone signed in and without anyone starting it.
- **FR-027**: System MUST continue correctly when a run is missed, catching up everyone who became due in the meantime on the next run.
- **FR-028**: System MUST NOT require a second machine, a separate service, or any component beyond what already runs the platform.

**Seeing notifications**

- **FR-029**: System MUST show a person, inside the platform, every notification created for them, newest first.
- **FR-030**: System MUST indicate in the application shell when a person has notifications they have not seen.
- **FR-031**: System MUST record when a person has seen a notification, and MUST stop indicating it thereafter.
- **FR-032**: System MUST let a person reach the module a notification concerns directly from it.
- **FR-033**: System MUST refuse any person access to another person's notifications.
- **FR-034**: System MUST keep the in-app list granular even where messages were combined, so a person overdue on three modules sees three entries.
- **FR-035**: System MUST let an instructor set, on a test that does not recur, a period within which it should be completed, counted from when each person was registered on the module.
- **FR-036**: System MUST treat a person who has not passed such a test by that point as due, and then overdue, using exactly the same reminders as a recurring test.
- **FR-037**: System MUST stop treating such a test as outstanding once the person passes it, and MUST NOT make it due again.
- **FR-038**: System MUST refuse a completion period on a test with no pass mark, for the same reason a retake interval is refused.
- **FR-039**: System MUST generate no due date and no reminder for a test that has neither a retake interval nor a completion period.

**Presentation**

- **FR-040**: System MUST present the notification list usably at phone, tablet, and desktop widths, with no sideways scrolling of the page itself.

### Key Entities

- **Notification**: A record that one person was told one thing about one module. Holds what kind of event it was, which module and due date it concerned, when it was created, when the person saw it, and when a message about it was sent. The combination of person, kind, module, and due date occurs at most once.
- **Retake interval** (an addition to **Test**, from Phase 2): how often that test must be retaken. Absent for a one-off test.
- **Completion period** (an addition to **Test**, from Phase 2): how long after being registered a person has to pass a one-off test. Absent where nobody is to be chased.
- **Due date**: not stored. Derived for each person and test — from their most recent attempt and the retake interval, or from their registration and the completion period.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person who last passed longer ago than the retake interval is shown as overdue, in 100% of cases.
- **SC-002**: A person who passed within the interval is never shown as due or overdue, in 100% of cases.
- **SC-003**: Running the daily process twice in one day produces no second notification record and no second message, in 100% of runs.
- **SC-004**: A person overdue on three modules receives one message and sees three entries in the platform, in 100% of cases.
- **SC-005**: A person who passes stops receiving reminders on the next run, in 100% of cases.
- **SC-006**: A missed run causes nobody to be skipped; the next run reaches everyone who became due in the meantime, in 100% of cases.
- **SC-007**: A notification whose message failed to send is retried on a later run, in 100% of cases.
- **SC-008**: Every notification a person receives by message also exists in their in-app list, in 100% of cases.
- **SC-009**: A person can reach another person's notifications in 0% of attempts.
- **SC-010**: Changing a test's retake interval re-dates every registered person without any further action, in 100% of cases.
- **SC-011**: An instructor sets a retake schedule for a module in under one minute, and does nothing further for it thereafter.
- **SC-012**: A trainee reaches the module a notification concerns in one action from the notification.
- **SC-013**: The notification list is readable at 360 pixels wide with no sideways page scrolling.
- **SC-014**: A person whose most recent attempt did not pass is shown as due, regardless of any earlier pass, in 100% of cases.
- **SC-015**: A one-off test with a completion period makes each person due at their own registration date plus that period, in 100% of cases.
- **SC-016**: A test with neither a retake interval nor a completion period generates no notification, in 100% of cases.
- **SC-017**: Every user-facing behaviour above is covered by an automated test that fails if the behaviour regresses.

## Assumptions

**Chosen defaults**, adopted because the phase description did not fix them and a reasonable default exists:

- A completion period is optional. An instructor who sets neither it nor a retake interval gets a test nobody is ever chased about, which is a legitimate choice for optional material.
- People are warned **fourteen days** before a due date, and reminded every **seven days** once overdue. Both configurable.
- The daily process runs early in the morning, so that anyone due is told before their working day rather than during it.
- Opening the notification list marks its entries as seen. There is no separate action to dismiss one.
- Notifications are never deleted. The list grows, which at this scale is not a problem worth solving in advance.
- Only the person concerned is notified. An instructor is not told when someone on their module becomes overdue — they see it on the module view built in Phase 3.
- A person registered on a module as its instructor is not subject to its retake schedule for that reason alone.

> **A consequence of running the clock from the most recent attempt.** Someone who passed, then retook the test to revise and scored below the pass mark, is due immediately and overdue the next day — and will be emailed about it. This is the same rule Phases 2 and 3 already apply, so the platform is at least consistent about it, and the review built in Phase 2 makes passing again straightforward. But it does mean casual revision has a cost, and people will notice.

**Dependencies**:

- Phase 1 for modules and registrations, Phase 2 for tests, pass marks, and attempts, Phase 3 for the state vocabulary this phase extends and the views these states appear in.
- Outbound email, already required since Phase 0 for sign-in codes. This phase is the first to send anything that is not a sign-in code.

**Deliberately excluded**, so that their absence is a decision rather than an oversight:

- Any way for a person to turn notifications off, choose which they receive, or unsubscribe. Mandatory training that can be silently muted is not mandatory.
- Notifying an instructor or administrator about anyone else's state.
- Any channel other than in-app and email — no SMS, no push, no calendar invitations.
- A queue, a worker process, or any second machine.
- Escalating to someone's manager, or any notion of a manager at all.
- Any grace period after a test is replaced. Everyone made due is notified on the next run.
- Reports or summaries of who was notified.
