"""Everything these pages show is derived. Nothing here writes.

No results table, no cached state, no summary row. Every figure comes from
registrations and attempts that already exist, so nothing can drift out of step
with what it came from (FR-025).

The queries are deliberately whole-set rather than per-module. The obvious
implementation, looping the registrations and querying each module's test and
each person's attempts, is thirty modules times three queries, and it looks fine
with three modules in testing (research R3).
"""

from __future__ import annotations

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models.attempt import Attempt
from app.models.module import Module
from app.models.registration import Registration
from app.models.test import Test
from app.models.user import User
from app.schemas.results import AttemptRow, CohortRow, CurrentTestRow, ModuleResultRow
from app.services import attempt_service, due, module_service, state


def current_test(db: DbSession, module_id: int) -> Test | None:
    """The module's currently published test, or None.

    Where more than one is published, the newest is the current one. State comes
    from this test alone: attempts at anything it replaced stay in the history
    but decide nothing (FR-008).
    """
    return db.exec(
        select(Test)
        .where(Test.module_id == module_id, Test.is_published == True)  # noqa: E712
        .order_by(Test.id.desc())
    ).first()


def current_test_row(db: DbSession, module_id: int) -> CurrentTestRow | None:  # noqa: D401
    """The same test, as something a template may be handed (done-gate 5)."""
    row = current_test(db, module_id)
    if row is None:
        return None
    return CurrentTestRow(id=row.id, title=row.title)


# ------------------------------------------------------------ a person's own


def for_person(db: DbSession, user: User) -> list[ModuleResultRow]:
    """Every module they hold a **trainee** registration on, and no other.

    A module somebody only instructs is not training they owe (FR-015).
    """
    registrations = db.exec(
        select(Registration).where(
            Registration.user_id == user.id,
            Registration.role_in_module == "trainee",
        )
    ).all()
    if not registrations:
        return []

    module_ids = [row.module_id for row in registrations]

    modules = {
        row.id: row
        for row in db.exec(
            select(Module).where(Module.id.in_(module_ids), Module.deleted_at.is_(None))
        ).all()
    }

    tests = db.exec(
        select(Test).where(Test.module_id.in_(module_ids), Test.is_published == True)  # noqa: E712
    ).all()
    current: dict[int, Test] = {}
    for row in tests:
        held = current.get(row.module_id)
        if held is None or row.id > held.id:
            current[row.module_id] = row

    attempts = db.exec(
        select(Attempt).where(
            Attempt.user_id == user.id,
            Attempt.test_id.in_([row.id for row in tests]) if tests else False,
        )
    ).all()
    by_test: dict[int, list[Attempt]] = {}
    for row in attempts:
        # Reading these pages is one of the moments an attempt past its ending
        # is submitted and scored. Without this a lapsed attempt would sit here
        # as "in progress" forever (Phase 2 research R8).
        by_test.setdefault(row.test_id, []).append(attempt_service.expire_if_due(db, row))

    rows: list[ModuleResultRow] = []
    for registration in registrations:
        module = modules.get(registration.module_id)
        if module is None:
            continue  # soft-deleted, so it is gone from every list

        test = current.get(module.id)
        mine = by_test.get(test.id, []) if test else []
        # Every row already holds what due.py needs, so the date is computed
        # here and handed to the same state function the other two views use
        # (Phase 4 FR-010).
        current_state = state.state_for(
            test, mine, due.due_date_for(test, registration, mine)
        )

        rows.append(
            ModuleResultRow(
                module_id=module.id,
                title=module.title,
                state=current_state.value,
                score_percent=state.score_for(mine),
                link=_link_for(current_state, module.id, mine),
            )
        )

    # Sorted in Python after grouping, so the state rule is never expressed a
    # second time in SQL (research R4).
    rows.sort(key=lambda row: (state.rank(state.State(row.state)), row.title))
    return rows


def _link_for(current_state: "state.State", module_id: int, attempts) -> str:
    """An attempt in progress leads back **into the attempt**, not to a review
    of something unfinished (FR-011)."""
    if current_state is state.State.IN_PROGRESS:
        open_attempt = next((row for row in attempts if not row.is_submitted), None)
        if open_attempt is not None:
            return f"/attempts/{open_attempt.id}"
    return f"/results/modules/{module_id}"


# --------------------------------------------------------- one module's history


def history_for(db: DbSession, subject: User, module_id: int, actor: User) -> list[AttemptRow]:
    """Every attempt this person made at this module's tests, newest first.

    **Including attempts at replaced tests**, which is the one place they remain
    visible (FR-008, FR-009).

    Subject and actor are separate arguments: a trainee may ask only for
    themselves, an instructor for anyone on a module they run (FR-018).
    """
    if subject.id != actor.id:
        module_service.get_for_write(db, module_id, actor)
    else:
        module_service.get_for(db, module_id, actor)

    tests = {
        row.id: row
        for row in db.exec(select(Test).where(Test.module_id == module_id)).all()
    }
    if not tests:
        return []

    live = current_test(db, module_id)
    live_id = live.id if live else None

    attempts = db.exec(
        select(Attempt)
        .where(Attempt.user_id == subject.id, Attempt.test_id.in_(tests.keys()))
        .order_by(Attempt.started_at.desc(), Attempt.id.desc())
    ).all()

    return [
        AttemptRow(
            attempt_id=row.id,
            test_title=tests[row.test_id].title,
            attempt_number=row.attempt_number,
            started_at=row.started_at,
            submitted_at=row.submitted_at,
            score_percent=row.score_percent,
            passed=row.passed,
            is_submitted=row.is_submitted,
            link=f"/attempts/{row.id}/review" if row.is_submitted else f"/attempts/{row.id}",
            at_replaced_test=row.test_id != live_id,
        )
        for row in attempts
    ]


# ------------------------------------------------------- the instructor's view


def for_module(db: DbSession, module_id: int, actor: User) -> list[CohortRow]:
    """Everyone registered as a trainee, with their state and score.

    Those who have not passed come first, then by name (FR-020).
    """
    module_service.get_for_write(db, module_id, actor)

    people = db.exec(
        select(Registration, User)
        .join(User, User.id == Registration.user_id)
        .where(
            Registration.module_id == module_id,
            Registration.role_in_module == "trainee",
        )
        .order_by(User.full_name)
    ).all()
    if not people:
        return []

    test = current_test(db, module_id)
    by_user: dict[int, list[Attempt]] = {}
    if test is not None:
        for row in db.exec(select(Attempt).where(Attempt.test_id == test.id)).all():
            by_user.setdefault(row.user_id, []).append(
                attempt_service.expire_if_due(db, row)
            )

    rows = [
        CohortRow(
            user_id=person.id,
            full_name=person.full_name,
            email=person.email,
            state=state.state_for(
                test,
                by_user.get(person.id, []),
                due.due_date_for(test, registration, by_user.get(person.id, [])),
            ).value,
            score_percent=state.score_for(by_user.get(person.id, [])),
            link=f"/modules/{module_id}/results/{person.id}",
        )
        for registration, person in people
    ]

    rows.sort(key=lambda row: (state.rank(state.State(row.state)), row.full_name))
    return rows


def count_affected_by_replacement(db: DbSession, module_id: int) -> int:
    """How many registered people currently show **passed**.

    Phase 2's publish route names this number before replacing a test, because
    "this will reset trainees" is ignored and "this will reset 30 people" is not
    (FR-027, research R6). It counts through the same state function, so the
    number warned about is the number that changes.
    """
    test = current_test(db, module_id)
    if test is None:
        return 0

    trainees = db.exec(
        select(Registration).where(
            Registration.module_id == module_id,
            Registration.role_in_module == "trainee",
        )
    ).all()
    if not trainees:
        return 0

    by_user: dict[int, list[Attempt]] = {}
    for row in db.exec(select(Attempt).where(Attempt.test_id == test.id)).all():
        by_user.setdefault(row.user_id, []).append(row)

    return sum(
        1
        for registration in trainees
        if state.state_for(
            test,
            by_user.get(registration.user_id, []),
            # The same due date the dashboard uses, so the number warned about
            # stays the number that changes: somebody already overdue does not
            # show as passed and is not counted as being reset.
            due.due_date_for(test, registration, by_user.get(registration.user_id, [])),
        )
        is state.State.PASSED
    )


def subject_on_module(db: DbSession, module_id: int, user_id: int) -> User | None:
    """The person a cohort row points at, or None if they are not on the module.

    Guards against an instructor typing an id for somebody who is not theirs to
    see, which would otherwise reach across module boundaries (FR-021).
    """
    registration = db.exec(
        select(Registration).where(
            Registration.module_id == module_id, Registration.user_id == user_id
        )
    ).first()
    if registration is None:
        return None
    return db.get(User, user_id)


def state_for_module(db: DbSession, module_id: int, user: User) -> str | None:
    """The caller's own state on one module, for the badge on its home page.

    Returns None where they hold no trainee registration, because the badge is
    about training they owe.
    """
    registration = db.exec(
        select(Registration).where(
            Registration.module_id == module_id,
            Registration.user_id == user.id,
            Registration.role_in_module == "trainee",
        )
    ).first()
    if registration is None:
        return None

    test = current_test(db, module_id)
    mine = (
        [
            attempt_service.expire_if_due(db, row)
            for row in db.exec(
                select(Attempt).where(
                    Attempt.test_id == test.id, Attempt.user_id == user.id
                )
            ).all()
        ]
        if test
        else []
    )
    return state.state_for(test, mine, due.due_date_for(test, registration, mine)).value
