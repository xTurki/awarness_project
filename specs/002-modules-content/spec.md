# Feature Specification: Modules, Content & Registration

**Feature Branch**: `002-modules-content`

**Created**: 2026-09-10

**Status**: Draft

**Input**: User description: "phase 1"

## Overview

Phase 1 of the SME Cybersecurity Awareness Training Platform. It introduces the thing the whole platform exists to deliver: a **module** — a subject an organisation wants its people to learn, holding the material they read and the people who must read it.

By the end of this phase an administrator can set up a module, an instructor can write its material and put people on it, and those people can find it and read it. No tests exist yet; assessment begins in Phase 2.

This phase depends on Phase 1 of nothing — it builds directly on the accounts, roles, and sign-in delivered in `specs/001-platform-foundation`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Set up a module and put someone in charge of it (Priority: P1)

An administrator creates a module for a subject the organisation needs covered — phishing awareness, say — and assigns an instructor to own it. Until that instructor has written something and the module is published, nobody else sees it.

**Why this priority**: Nothing else in the phase can happen first. Every page, every registration, and every later test hangs off a module existing and having an owner.

**Independent Test**: As an administrator, create a module, assign an instructor, and confirm that instructor now sees it in their own list while trainees do not.

**Acceptance Scenarios**:

1. **Given** an administrator, **When** they create a module with a title and description, **Then** it exists in an unpublished state and appears in their list of modules.
2. **Given** an unpublished module, **When** an administrator assigns an instructor to it, **Then** that instructor sees it among their own modules.
3. **Given** an unpublished module with an instructor assigned, **When** a trainee looks at their modules, **Then** it does not appear and cannot be reached by requesting its address directly.
4. **Given** a module with content, **When** an administrator publishes it, **Then** registered trainees can see and open it.
5. **Given** a published module, **When** an administrator unpublishes it, **Then** trainees can no longer open it while the instructor still can.
6. **Given** an instructor or a trainee, **When** they attempt to create a module, **Then** they are refused.

---

### User Story 2 - Write the module's material (Priority: P1)

The instructor who owns a module writes its content inside the platform: several pages, in an order they choose, with headings, lists, links, and images. They can leave a page as a draft while the earlier ones are already live.

**Why this priority**: A module with no material is not something anyone can be asked to learn from. This is the phase's substance, and it is the largest single piece of work in it.

**Independent Test**: As an instructor, write three pages in a module, reorder them, leave one as a draft, put an image in another, and confirm a registered trainee sees exactly the two published pages in the chosen order with the image visible.

**Acceptance Scenarios**:

1. **Given** an instructor on their own module, **When** they create a page with a title and body, **Then** it is saved as a draft and appears in their page list.
2. **Given** an instructor writing a page, **When** they apply headings, emphasis, lists, and links, **Then** the formatting is preserved and shown to trainees as written, without them typing any markup.
3. **Given** several pages, **When** the instructor changes their order, **Then** trainees see them in the new order.
4. **Given** a page left as a draft, **When** a registered trainee opens the module, **Then** that page is absent from their view entirely.
5. **Given** a published page, **When** the instructor unpublishes it, **Then** it disappears from the trainee view while remaining editable.
6. **Given** an instructor, **When** they submit a page body containing a script, an event handler, or a dangerous link, **Then** what is stored has those removed — not merely hidden or escaped when displayed.
7. **Given** an instructor on someone else's module, **When** they attempt to add or edit a page, **Then** they are refused.
8. **Given** a page holding a full training topic of several thousand words, **When** it is saved, **Then** nothing is silently truncated.

---

### User Story 3 - Put people on a module (Priority: P2)

An administrator or the module's own instructor registers people onto it — one at a time, or several in one action — and removes people who should no longer be on it.

**Why this priority**: Material nobody is registered on reaches nobody. This is what turns a written module into training someone is actually expected to do.

**Independent Test**: Register five trainees onto a module in one action, confirm all five see it, remove one, and confirm that person no longer sees it while the other four still do.

**Acceptance Scenarios**:

1. **Given** an instructor on their own module, **When** they register a trainee, **Then** that person sees the module among theirs.
2. **Given** an instructor, **When** they select several people and register them in one action, **Then** all of them are registered.
3. **Given** a registered trainee, **When** the instructor removes their registration, **Then** they no longer see the module and cannot reach it directly.
4. **Given** someone already registered, **When** they are registered again, **Then** no duplicate is created and no error is shown to the person doing it.
5. **Given** an instructor, **When** they view their module's roster, **Then** they see everyone registered on it and in what capacity.
6. **Given** an instructor, **When** they attempt to view the roster of a module they do not own, **Then** they are refused.
7. **Given** a registered trainee, **When** they look for a way to remove their own registration, **Then** none is offered.

---

### User Story 4 - Find and read your training (Priority: P2)

A trainee signs in, sees the modules they have been put on, opens one, and reads its pages in order on whatever device they have.

**Why this priority**: It is the entire point of the phase from the perspective of the person the platform exists for. It cannot be built before there is something to read, which is why it is not P1.

**Independent Test**: As a registered trainee, sign in, open a module from the dashboard, and read through its published pages on a phone and on a desktop.

**Acceptance Scenarios**:

1. **Given** a signed-in trainee registered on three modules, **When** they view their dashboard, **Then** they see those three and no others.
2. **Given** a trainee opening a module, **When** the module page loads, **Then** they can move between its published pages in the instructor's order.
3. **Given** a trainee on a phone, **When** they open a module, **Then** the navigation is reachable as a drawer and the page does not scroll sideways.
4. **Given** a trainee on a desktop, **When** they open a module, **Then** the navigation is visible alongside the content without being opened first.
5. **Given** a trainee not registered on a module, **When** they request its address directly, **Then** they are refused.

---

### Edge Cases

- **A module needs to be retired.** There is no archive. The administrator unpublishes it, which removes it from trainees' view while leaving its content, its pages, and its registrations intact and restorable by publishing again.
- **An instructor is removed from a module they were writing.** They lose access to it immediately, including to pages they authored. The pages remain with the module.
- **The last instructor is removed from a module.** The module continues to exist with an administrator able to assign a replacement; no content is lost.
- **A page is deleted while a trainee is reading it.** The trainee's next move within the module finds it gone and returns them to the module's first available page rather than an error.
- **Reordering while someone is reading.** The trainee sees the new order on their next page load. Nothing they are currently reading disappears.
- **An oversized image.** The instructor is told the file is too large and by how much, rather than the upload failing without explanation.
- **An image used on a page that is later deleted.** The image remains stored and unreferenced. Deleting the whole module removes it.
- **A module with no pages at all.** It can be published. A trainee opening it sees an empty module rather than an error, and the instructor is warned before publishing it empty.
- **Two instructors editing the same page.** The later save wins. Nothing is merged and nothing warns them — accepted for this phase.
- **A trainee registered on a module whose only pages are drafts.** They see the module with no readable content, not an error.

## Requirements *(mandatory)*

### Functional Requirements

**Modules**

- **FR-001**: System MUST let an administrator create a module with a title and a description. A module has no code or reference number; its title identifies it.
- **FR-002**: Every module MUST be in exactly one of two states: unpublished or published. There is no archived state — a module does not come to an end.
- **FR-003**: System MUST let an administrator publish and unpublish a module.
- **FR-004**: System MUST let an administrator assign one or more instructors to a module, and remove them.
- **FR-005**: System MUST restrict creating, publishing, unpublishing, and assigning instructors to administrators.
- **FR-006**: System MUST show an administrator every module in any state.
- **FR-007**: System MUST show an instructor only the modules they are assigned to, including unpublished ones, since that is how they build them.
- **FR-008**: System MUST show a trainee every published module on which they hold a registration, for as long as that registration exists. A module remains available indefinitely; it is retired by unpublishing it, not by any separate lifecycle state.
- **FR-009**: System MUST verify the caller's relationship to a module before any module-scoped action, at the point of request rather than by hiding controls.
- **FR-010**: Removing a module MUST be reversible from within the platform; permanent removal MUST require direct access to the data.

**Module content**

- **FR-011**: System MUST let an instructor create, edit, and delete pages within a module they are assigned to.
- **FR-012**: Every page MUST have a title, a body, a position among its siblings, and its own draft or published state.
- **FR-013**: System MUST let an instructor change the order of pages within a module.
- **FR-014**: System MUST show trainees only published pages, in the order the instructor set.
- **FR-015**: System MUST let an instructor produce headings, emphasis, lists, and links without writing markup by hand.
- **FR-016**: System MUST remove scripts, event handlers, and dangerous link targets from submitted page content **before storing it**. Sanitising in the editor, or when displaying, is not a substitute.
- **FR-017**: System MUST accept a page body large enough for a complete training topic and MUST NOT truncate one silently.
- **FR-018**: System MUST restrict authoring a module's content to instructors assigned to that module, and to administrators.

**Images**

- **FR-019**: System MUST let an instructor upload an image for use in a page of a module they are assigned to.
- **FR-020**: System MUST NOT provide any means for a trainee to upload a file of any kind.
- **FR-021**: System MUST accept only image files, by extension, and MUST enforce a maximum upload size, telling the instructor clearly when a file is rejected.
- **FR-022**: System MUST delete a module's uploaded images when that module is permanently removed.

**Registration**

- **FR-023**: System MUST let an administrator register and remove any person on any module.
- **FR-024**: System MUST let an instructor register and remove trainees on modules they are assigned to.
- **FR-025**: System MUST let several people be registered in a single action.
- **FR-026**: System MUST record a person's capacity on a module — instructor or trainee — independently of their platform-wide role, so the same person may be an instructor on one module and a trainee on another.
- **FR-027**: System MUST NOT create a duplicate when someone already registered is registered again.
- **FR-028**: System MUST NOT provide any way for a person to register themselves on a module, or to remove their own registration. People are put on modules by an administrator or by the module's instructor, and taken off the same way.
- **FR-029**: System MUST let an instructor see the roster of a module they are assigned to, and MUST refuse the roster of any other module.
- **FR-030**: A registration either exists or it does not. System MUST NOT carry intermediate registration states — nothing is invited and awaiting acceptance, and nothing is concluded, because people are registered directly and modules do not end.

**Finding and reading**

- **FR-031**: System MUST list on a trainee's dashboard every module they hold an active registration on and no others.
- **FR-032**: System MUST give each module a home view from which its readable pages can be reached.
- **FR-033**: System MUST present module navigation as persistent alongside the content on desktop widths, and as an openable drawer at phone widths.
- **FR-034**: System MUST present every screen in this phase usably at phone, tablet, and desktop widths, with no sideways scrolling of the page itself.
- **FR-035**: System MUST make content and any assessment reachable independently — reading the material MUST NOT be a precondition for anything else.

### Key Entities

- **Module**: A subject the organisation wants covered. Holds a title, a description, and whether it is published. Owns its pages, its images, and its registrations. It has no end date and no completed state — it stays available and is retaken periodically once Phase 4 adds retake intervals.
- **Page**: One section of a module's material. Holds a title, a body of formatted text, its position among the module's other pages, and whether it is a draft or published. Belongs to exactly one module.
- **Content image**: A picture an instructor uploaded for use in a page. Records the name it is stored under, the name it arrived with, its type and size, who uploaded it, and when. Belongs to a module.
- **Registration**: The fact that a particular person is on a particular module, and in what capacity — instructor or trainee. Records when it began. It carries no status of its own: it exists, or the person is not on the module.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An administrator creates a module and assigns an instructor to it in under two minutes.
- **SC-002**: An instructor with prepared text writes and publishes a three-page module, including one image, in under fifteen minutes.
- **SC-003**: A trainee registered on a module reaches its first page from signing in within three actions.
- **SC-004**: Page content containing a script or an event handler is stored with those removed, verified by inspecting what was stored rather than what is displayed.
- **SC-005**: A trainee sees draft pages in 0% of cases.
- **SC-006**: A person not registered on a module can reach no part of it, including by requesting addresses directly, in 100% of attempts.
- **SC-007**: An instructor can reach no part of a module they are not assigned to, in 100% of attempts.
- **SC-008**: Registering five people in one action takes one submission and under thirty seconds.
- **SC-009**: Every screen in this phase is usable at 360 pixels wide with no sideways page scrolling, and at tablet and desktop widths.
- **SC-010**: A trainee can neither put themselves on a module nor take themselves off one, in 100% of attempts, because no such route exists.
- **SC-011**: A page holding five thousand words is stored and redisplayed without loss.
- **SC-012**: Removing a module and restoring it returns its pages, images, and registrations intact.
- **SC-013**: Unpublishing a module and publishing it again returns it to trainees with its pages, images, and registrations unchanged.
- **SC-014**: Every user-facing behaviour above is covered by an automated test that fails if the behaviour regresses.

## Assumptions

**Chosen defaults**, adopted because the phase description did not fix them and a reasonable default exists:

- Modules are created by administrators only. Instructors write and run modules but do not create them. Confirmed deliberately: in an organisation this size the administrator and the instructor are often the same person, so the bottleneck is theoretical.
- A module may have more than one instructor. Nothing requires it, but nothing is gained by forbidding it, and a single-instructor rule would have to be undone the first time someone goes on holiday.
- The maximum upload size is five megabytes per image — comfortably more than a screenshot or diagram needs, comfortably less than a video.
- Accepted image types are the ordinary web formats, checked by file extension.
- "Several thousand words" for FR-017 means a page limit generous enough that an instructor will not meet it while writing prose; the failure mode that matters is silent truncation, not the exact ceiling.
- Bulk registration means selecting several existing people and registering them together. It does not mean importing a file — that remains out of scope.
- **Modules are never archived and never conclude.** Training in an SME is continuous: a module stays available and its test is retaken on a cycle rather than the module being closed off. Retiring one means unpublishing it. This removes the archived state the earlier draft carried, and with it every question about what an archived module means for the people on it.
- **A registration has no status.** With no invitation to accept and no module completion to record, states such as "invited" and "concluded" had nothing that could produce them. A person is on a module or is not.
- Publishing a module with no pages is permitted but warned about, on the grounds that an empty module is more likely a mistake than an intention.
- Concurrent edits to the same page are resolved last-write-wins with no warning. Two instructors on one page at the same moment is rare enough in an organisation this size to accept losing the earlier edit.

**Dependencies**:

- Everything in `specs/001-platform-foundation` — accounts, the three roles, sign-in, and the application shell — must exist first. This phase adds no new way to sign in and no new kind of person.
- File storage becomes part of the platform for the first time in this phase, for instructor image uploads only.

**Deliberately excluded**, so that their absence is a decision rather than an oversight:

- Any assessment. No questions, no tests, no scores — that is Phase 2.
- Prerequisites or completion gating. Content and assessment are always both reachable; there is no "read this before that", no tracking of which pages a trainee has opened, and no unlock rules.
- Any form of self-registration. A person cannot put themselves on a module, and there is no page listing modules they are not on. Training here is assigned, not chosen.
- Grouping modules into pathways, tracks, or sequences.
- Uploading anything by a trainee, and uploading anything other than images by an instructor.
- Importing a roster from a file.
- Copying or duplicating a module.
- Archiving a module, or any lifecycle state beyond published and unpublished.
- Marking a registration, or a module, as completed or concluded.
- Any record of who changed what, in keeping with the platform carrying no audit trail.
- Notifying anyone that they have been registered on a module — notifications arrive in Phase 4.
