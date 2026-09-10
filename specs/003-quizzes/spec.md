# Feature Specification: Quizzes, Question Banks, Attempts & Scoring

**Feature Branch**: `003-quizzes`

**Created**: 2026-09-10

**Status**: Draft

**Input**: User description: "phase 2"

## Overview

Phase 2 of the SME Cybersecurity Awareness Training Platform. Modules can now be read; this phase makes them assessable.

An instructor builds a bank of multiple-choice questions for their module, assembles them into a test, sets a pass mark, and publishes it. A trainee takes the test and gets a score immediately.

**This is the largest and most fragile phase in the project.** Everything else either fails visibly or fails harmlessly. Here, a trainee can lose twenty minutes of work to a dropped connection, and the platform can be wrong about whether someone passed. The attempt model in this specification is written to make both impossible.

## Clarifications

### Session 2026-09-10

- Q: When a trainee takes a test, do they see all the questions on one scrolling page, or one question at a time with next and previous? → A: All on one scrolling page

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Build a test (Priority: P1)

An instructor writes questions for their module, chooses which of them make up a test, sets how long it runs, when it is open, how many attempts are allowed, and the mark needed to pass. Then they publish it.

**Why this priority**: Nothing can be taken until something has been built. It is also the smaller half of the phase, and the half with no moving parts at runtime.

**Independent Test**: As an instructor, write ten questions, assemble them into a test with a pass mark of 80%, publish it, and confirm a registered trainee can see it.

**Acceptance Scenarios**:

1. **Given** an instructor on their own module, **When** they write a question with a prompt, several options, and at least one marked correct, **Then** it is saved to that module's question bank.
2. **Given** a question being written, **When** fewer than two options are given, or no option is marked correct, **Then** it is refused with a message saying what is missing.
3. **Given** a question bank, **When** the instructor assembles a test from selected questions, **Then** those questions belong to that test in the order chosen.
4. **Given** a test being built, **When** the instructor sets a time limit, an opening and closing time, a number of attempts, and a pass mark, **Then** all are saved and shown to trainees before they start.
5. **Given** an unpublished test, **When** a registered trainee looks at the module, **Then** they cannot see or start it.
6. **Given** a published test inside its availability window, **When** a registered trainee opens the module, **Then** they can start it.
7. **Given** an instructor, **When** they attempt to add questions to a module they are not assigned to, **Then** they are refused.
8. **Given** a test that one person has already attempted, **When** the instructor tries to change any part of it, **Then** they are refused and told the test is frozen because it has been attempted.
9. **Given** a frozen test, **When** the instructor unpublishes it and builds a replacement, **Then** the original attempts keep their scores and remain viewable.

---

### User Story 2 - Take a test and know the result (Priority: P1)

A trainee opens a published test, answers its questions, submits, and is told their score and whether they passed, immediately, with no waiting for anyone.

**Why this priority**: This is the phase. Everything the platform exists to do converges here, and it is what produces the scores Phase 3 displays and Phase 4 schedules around.

**Independent Test**: As a registered trainee, take a ten-question test, submit it, and confirm the score and pass or fail appear at once and match the answers given.

**Acceptance Scenarios**:

1. **Given** a published test within its window, **When** a registered trainee starts it, **Then** an attempt begins and every question is shown on one scrolling page, with the submit control at the end.
2. **Given** a question with one correct option, **When** it is presented, **Then** the trainee may select exactly one answer.
3. **Given** a question with several correct options, **When** it is presented, **Then** the trainee may select more than one.
4. **Given** a completed test, **When** the trainee submits it, **Then** a score and a pass-or-fail outcome appear immediately.
5. **Given** a question with several correct options, **When** the trainee selects some but not all of them, **Then** that question scores nothing, there is no partial credit.
6. **Given** a trainee who has used all permitted attempts, **When** they try to start another, **Then** they are refused and told why.
7. **Given** a test outside its availability window, **When** a trainee tries to start it, **Then** they are refused.
8. **Given** a trainee not registered on the module, **When** they request the test directly, **Then** they are refused.
9. **Given** a test with shuffling switched on, **When** two trainees take it, **Then** each sees the questions in a different order.

---

### User Story 3 - Survive an interruption (Priority: P1)

A trainee is twelve questions into a timed test when their connection drops, their phone locks, or they close the tab by accident. They come back and continue from where they were, with the right amount of time left.

**Why this priority**: Equal to taking the test at all. A platform that loses someone's work mid-test will not be used twice, and mandatory training is exactly the setting where people take tests on unreliable phone connections.

**Independent Test**: Start an attempt, answer several questions, kill the browser, reopen, and confirm every answer given is still there and the remaining time reflects real elapsed time rather than restarting.

**Acceptance Scenarios**:

1. **Given** a trainee answering questions, **When** each answer is given, **Then** it is recorded at that moment rather than only on submission.
2. **Given** an attempt interrupted at any point, **When** the trainee returns, **Then** every answer already given is still recorded and shown.
3. **Given** an interrupted attempt on a timed test, **When** the trainee returns, **Then** the time remaining is what actually remains since they started, not a fresh allowance.
4. **Given** a resumed attempt on a shuffled test, **When** it is displayed again, **Then** the questions appear in the same order as before the interruption.
5. **Given** an attempt whose time has run out, **When** the trainee tries to answer or submit, **Then** it is refused and the attempt is treated as submitted with whatever was answered.
6. **Given** an instructor changes a test's time limit, **When** an attempt is already running, **Then** that attempt keeps the deadline it was given when it started.
7. **Given** an attempt abandoned entirely, **When** its time has passed, **Then** it is scored on what was answered rather than remaining open indefinitely.

---

### User Story 4 - Look back at what you did (Priority: P2)

After submitting, a trainee can look at the attempt they just made, what they answered, what they scored, and whether they passed.

**Why this priority**: Awareness training that tells someone only a number teaches nothing. It also matters for recurring training, where the same person meets the same subject again.

**Independent Test**: Complete an attempt, open its review, and confirm the trainee sees their own answers and result, and cannot see anyone else's.

**Acceptance Scenarios**:

1. **Given** a submitted attempt, **When** the trainee opens its review, **Then** they see each question, the answer they gave, and whether it was right.
2. **Given** a trainee with several attempts at the same test, **When** they look at their history, **Then** they see each attempt with its date and score.
3. **Given** a trainee who scored 40, then 90, then 70, **When** their result is shown anywhere, **Then** it is 70, the most recent, and the earlier two remain in their history.
4. **Given** a submitted attempt, **When** the trainee reviews it, **Then** each question shows their answer, whether it was right, and the correct answer.
3. **Given** a trainee, **When** they request another person's attempt directly, **Then** they are refused.
4. **Given** an attempt still in progress, **When** the trainee opens the review, **Then** they are returned to the attempt rather than shown a partial result.

---

### User Story 5 - Check on the people taking it (Priority: P2)

An instructor opens their test and sees the attempts made on it, who has taken it, what they scored, whether they passed. Where a question turns out to have been wrong or unfair, the instructor corrects that attempt's score by hand.

**Why this priority**: An automatically scored test with no human override is a test whose mistakes cannot be undone. Instructors need a way to fix a bad question's consequences without rebuilding anything.

**Independent Test**: As an instructor, view the attempts on your own test, change one attempt's score, and confirm the new score and its pass-or-fail outcome are what the trainee now sees.

**Acceptance Scenarios**:

1. **Given** an instructor on their own module, **When** they open a test's attempts, **Then** they see each trainee's attempts with dates, scores, and pass-or-fail outcomes.
2. **Given** an instructor viewing an attempt, **When** they open it, **Then** they see the answers that trainee gave.
3. **Given** an instructor, **When** they set a different score on an attempt, **Then** that score replaces the automatic one and the pass-or-fail outcome follows from it.
4. **Given** an overridden score, **When** the trainee views their result, **Then** they see the corrected score.
5. **Given** an instructor, **When** they request attempts on a module they are not assigned to, **Then** they are refused.

---

### Edge Cases

- **The availability window closes mid-attempt.** The attempt ends at whichever comes first, the time limit or the closing time, and is scored on what was answered.
- **A test with no questions.** It cannot be published; the instructor is told why.
- **An instructor needs to fix a test that people have already taken.** They cannot. The test is frozen from its first attempt onward. They unpublish it and build a replacement, and the old attempts keep their meaning because the test that produced them never changed.
- **Two devices, one attempt.** The same trainee opens their in-progress attempt on a phone and a laptop. Both write to the same attempt; the last answer given to any question is the one that counts.
- **Submitting twice.** The second submission is ignored rather than creating a second result.
- **Every answer left blank.** The attempt submits and scores zero. It is a completed attempt, not an absent one.
- **A pass mark higher than the total available.** Refused when the test is saved.
- **An attempt started just before the window closes.** Permitted, the window governs starting, and the rule above governs the ending.
- **The clock on the trainee's device is wrong.** Irrelevant. Time remaining is decided by the platform, and the countdown shown is decoration.
- **An instructor overrides a score on an attempt still in progress.** Refused; only finished attempts can be corrected.

## Requirements *(mandatory)*

### Functional Requirements

**Question bank**

- **FR-001**: System MUST let an instructor create, edit, and delete questions within a module they are assigned to.
- **FR-002**: Every question MUST have a prompt, a number of points, and a position among the others.
- **FR-003**: Every question MUST offer at least two answer options, of which at least one is marked correct, validated when the question is saved.
- **FR-004**: System MUST allow more than one option to be marked correct.
- **FR-005**: System MUST present a question offering one correct answer as a single choice, and a question offering several as a multiple choice, without the instructor having to say which.
- **FR-006**: System MUST restrict the question bank of a module to instructors assigned to it, and to administrators.

**Building a test**

- **FR-007**: System MUST let an instructor assemble a test from questions in their module's bank, in an order they control.
- **FR-008**: System MUST let an instructor set, for each test: a title, instructions, an opening and closing time, a time limit, the number of attempts allowed, whether questions are shuffled, and the mark needed to pass.
- **FR-009**: System MUST show a trainee the time limit, attempts allowed, and pass mark before they start.
- **FR-010**: System MUST let an instructor publish and unpublish a test, and MUST hide unpublished tests from trainees entirely.
- **FR-011**: System MUST refuse to publish a test that has no questions.
- **FR-012**: System MUST refuse a pass mark that could not be reached with the points available.
- **FR-013**: System MUST prevent any change to a test or to the questions in it once a single attempt has been made at it, no adding, removing, reordering, or rewording, and no change to its pass mark or scoring. An instructor who needs a different test MUST create one.
- **FR-014**: System MUST tell an instructor clearly why a test can no longer be edited, and MUST let them unpublish it so that no further attempts are made at it.

**Taking a test**

- **FR-015**: System MUST allow an attempt to begin only when the test is published, the person holds a registration on its module, the current time is inside the availability window, and they have attempts remaining.
- **FR-016**: System MUST fix an attempt's ending moment when it begins, and MUST NOT change it if the instructor later alters the test's time limit.
- **FR-017**: System MUST fix the order of questions when an attempt begins, and MUST present that same order every time the attempt is resumed.
- **FR-018**: System MUST record each answer at the moment it is given, independently of every other answer and of submission.
- **FR-019**: System MUST allow an interrupted attempt to be resumed with every answer already given still present.
- **FR-020**: System MUST calculate time remaining from when the attempt began, using its own clock, and MUST treat any time shown on the trainee's device as display only.
- **FR-021**: System MUST refuse to record an answer after the attempt's ending moment has passed.
- **FR-022**: System MUST treat an attempt whose ending moment has passed as submitted, scored on the answers it holds.
- **FR-023**: System MUST end an attempt at whichever comes first, its time limit or the test's closing time.
- **FR-024**: System MUST ignore a second submission of an attempt already submitted.
- **FR-025**: System MUST record how many attempts a person has made at a test, and MUST refuse a further one beyond the number allowed.

**Scoring**

- **FR-026**: System MUST score every submitted attempt without human involvement and MUST produce the score immediately.
- **FR-027**: System MUST award a question's points only when the selected answers exactly match the correct ones, no partial credit for a partly correct answer.
- **FR-028**: System MUST express a result both as a score and as a pass or fail decided against the test's pass mark.
- **FR-029**: System MUST treat a person's **most recent** submitted attempt as the one that represents them, for their score, their pass-or-fail outcome, and anything later phases read. Earlier attempts remain visible in their history but do not stand for them.

**Reviewing**

- **FR-030**: System MUST let a trainee see their own submitted attempts, with the date, score, and outcome of each.
- **FR-031**: System MUST show a trainee, for every question in their submitted attempt, the answer they gave, whether it was correct, and **the correct answer**.
- **FR-032**: System MUST refuse a trainee access to anyone else's attempt.
- **FR-033**: System MUST let an instructor see every attempt made on a test in a module they are assigned to, including the answers given.
- **FR-034**: System MUST refuse an instructor access to attempts on any module they are not assigned to.
- **FR-035**: System MUST let an instructor replace an attempt's score with one of their own, after which the pass-or-fail outcome follows the new score.
- **FR-036**: System MUST refuse a score override on an attempt that has not been submitted.

**Throughout**

- **FR-037**: System MUST present every screen in this phase usably at phone, tablet, and desktop widths, with no sideways scrolling of the page itself.
- **FR-038**: System MUST make taking a test possible with a whole answer option tappable, not only a small control beside it.
- **FR-039**: System MUST keep content and tests independently reachable, reading a module's pages MUST NOT be a precondition for starting its test.

### Key Entities

- **Question**: Something asked, belonging to one module's bank. Holds its prompt, what it is worth, and its position. Owns its answer options.
- **Answer option**: One of the choices offered for a question, and whether it is correct.
- **Test**: A set of questions drawn from a module's bank, with the rules for taking it, when it is open, how long it runs, how many attempts, whether questions shuffle, and the mark needed to pass. Belongs to one module.
- **Attempt**: One person's sitting of one test. Records when it began, when it must end, when it was submitted, whether it is in progress or finished, the order of questions it was given, and its score. The ending moment and the question order are fixed when it begins and never change afterwards.
- **Answer given**: What a person chose for one question in one attempt, whether it was right, and what it earned. At most one per question per attempt.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An instructor with prepared material writes ten questions and publishes a test from them in under twenty minutes.
- **SC-002**: A trainee submitting a test sees their score and outcome within two seconds.
- **SC-003**: An attempt interrupted at any point loses at most the single answer being given at that moment, in 100% of interruptions.
- **SC-004**: A resumed attempt shows time remaining within five seconds of the true elapsed time, in 100% of resumptions.
- **SC-005**: A resumed shuffled attempt shows questions in the same order as before the interruption, in 100% of resumptions.
- **SC-006**: An answer submitted after an attempt's ending moment is refused in 100% of attempts.
- **SC-007**: Scores computed by the platform match the answers given in 100% of attempts, verified against a set of worked examples covering single-answer, multi-answer, blank, and fully wrong cases.
- **SC-008**: A trainee can reach another person's attempt in 0% of attempts.
- **SC-009**: An instructor can reach attempts on a module they are not assigned to in 0% of attempts.
- **SC-010**: A trainee exceeding the permitted number of attempts is refused in 100% of attempts.
- **SC-011**: A test that has been attempted cannot be altered through any route in the platform, in 100% of attempts.
- **SC-012**: Every screen in this phase is usable at 360 pixels wide with no sideways page scrolling.
- **SC-013**: A ten-question test can be taken start to finish on a phone without zooming or horizontal scrolling.
- **SC-014**: Every user-facing behaviour above is covered by an automated test that fails if the behaviour regresses.

## Assumptions

**Chosen defaults**, adopted because the phase description did not fix them and a reasonable default exists:

- A score is expressed as a percentage of the points available, and the pass mark is a percentage too. Points per question exist so an instructor can weight a hard question, not so trainees are shown raw totals.
- Shuffling reorders questions, not the options within a question. The setting is named for questions and that is what it does.
- An attempt with no answers at all is still an attempt: it submits, scores zero, and counts against the attempts allowed.
- The availability window governs when an attempt may *start*. An attempt that started inside the window runs to its own ending moment even if the window closes first, subject to the rule that the window's close also ends it, whichever comes first.
- A trainee may have only one attempt in progress at a time on a given test. Opening it on a second device continues the same attempt rather than starting another.
- A test is frozen from its first attempt. Before that it may be edited freely; after it, not at all.
- **A test is one scrolling page.** Every question is shown at once, in the attempt's fixed order, with submit at the end. There is no per-question navigation and no separate review screen, a trainee checks what they left blank by scrolling. The countdown stays visible while scrolling.
- Instructions on a test are plain text. The rich-text editor built in Phase 1 is for module content, not for question prompts.

> **A consequence of two of these decisions together.** The most recent attempt represents a person, and a review shows the correct answers. So someone can fail, read the answers, retake, and pass, and in Phase 4, where recurring tests allow unlimited retakes, that path is always open. The pass mark therefore measures that someone has seen the right answers and can reproduce them, not that they knew them unaided. For awareness training that is arguably the point; it is recorded here so it is a choice rather than a surprise.

**Dependencies**:

- Phase 1 must exist first: modules, the people registered on them, and the rule that only an instructor assigned to a module may change anything in it. This phase adds no new kind of person and no new way to sign in.
- Nothing here depends on Phase 3 or 4. The scores this phase produces are what those phases read.

**Deliberately excluded**, so that their absence is a decision rather than an oversight:

- Any question type other than multiple choice. No short answer, no essays, no matching, no ordering, and therefore nothing that waits on a human to mark it.
- Partial credit.
- Drawing a random subset of questions from the bank for each attempt. A test is a fixed set of questions.
- Question categories, tags, or difficulty levels.
- Requiring a trainee to read the module's content before the test unlocks.
- Recurring retake intervals and the notifications around them. `retake_interval_days` and everything that reads it arrive in Phase 4; in this phase the attempts allowed is the only limit on retaking.
- Any record of who changed a question or overrode a score, in keeping with the platform carrying no audit trail.
