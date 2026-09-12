"""The results pages, against real rows.

Everything asserted here is derived. Nothing this phase adds writes, which is
what `test_no_new_storage` at the end exists to keep true.
"""

from __future__ import annotations

import pytest

from app.models.module import Module
from app.models.registration import Registration
from app.schemas.quiz import QuestionWrite, ScoreOverride, TestWrite
from app.services import (
    attempt_service,
    module_service,
    question_service,
    results_service,
    test_service,
)


@pytest.fixture()
def admin(make_user):
    return make_user(email="a@example.com", role="administrator")


@pytest.fixture()
def make_module(db):
    def _make(title, published=True):
        row = Module(title=title, is_published=published)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    return _make


@pytest.fixture()
def owner(db, make_user):
    return make_user(email="owner@example.com", role="instructor")


def _enrol(db, user, module, role="trainee"):
    db.add(Registration(user_id=user.id, module_id=module.id, role_in_module=role))
    db.commit()


def _build_test(db, owner, module, title="Check", mark=80, published=True):
    questions = [
        question_service.create_question(
            db, owner, module.id,
            QuestionWrite(prompt=f"{title} Q{n}?", points=1, options=["right", "wrong"], correct=[0]),
        )
        for n in (1, 2)
    ]
    created = test_service.create(
        db, owner, module.id,
        TestWrite(
            title=title, allowed_attempts=5, passing_score=mark,
            question_ids=[q.id for q in questions],
        ),
    )
    if published:
        test_service.set_published(db, owner, created.id, True)
    return created, questions


def _sit(db, trainee, test_id, questions, right):
    row = attempt_service.start(db, trainee, test_id)
    for question in questions[:right]:
        correct = [o.id for o in question.options if o.is_correct]
        attempt_service.save_answer(db, trainee, row.id, question.id, correct)
    return attempt_service.submit(db, row)


# ------------------------------------------------------- a trainee's dashboard


def test_the_list_holds_exactly_their_trainee_registrations(
    db, make_module, make_user, owner
):
    trainee = make_user(email="t@example.com", role="trainee")
    mine = make_module("Phishing")
    theirs = make_module("Passwords")
    _enrol(db, trainee, mine)

    rows = results_service.for_person(db, trainee)

    assert [row.title for row in rows] == ["Phishing"]
    assert theirs.title not in [row.title for row in rows]


def test_a_module_they_only_instruct_is_not_training_they_owe(db, make_module, owner):
    """FR-015. It appears in their module list, not in what they must complete."""
    module = make_module("Phishing")
    _enrol(db, owner, module, role="instructor")

    assert results_service.for_person(db, owner) == []


def test_a_module_with_no_published_test_reads_no_test_available(
    db, make_module, make_user
):
    trainee = make_user(email="t@example.com", role="trainee")
    module = make_module("Phishing")
    _enrol(db, trainee, module)

    rows = results_service.for_person(db, trainee)
    assert rows[0].state == "no test available"
    assert rows[0].score_percent is None


def test_the_four_states_across_four_modules(db, make_module, make_user, owner):
    trainee = make_user(email="t@example.com", role="trainee")

    never = make_module("Never attempted")
    running = make_module("In progress")
    passing = make_module("Passed")
    failing = make_module("Failed")

    for module in (never, running, passing, failing):
        _enrol(db, owner, module, role="instructor")
        _enrol(db, trainee, module)

    _build_test(db, owner, never)

    live, questions = _build_test(db, owner, running)
    attempt_service.start(db, trainee, live.id)  # left open

    live, questions = _build_test(db, owner, passing)
    _sit(db, trainee, live.id, questions, right=2)

    live, questions = _build_test(db, owner, failing)
    _sit(db, trainee, live.id, questions, right=0)

    by_title = {row.title: row for row in results_service.for_person(db, trainee)}

    assert by_title["Never attempted"].state == "not started"
    assert by_title["In progress"].state == "in progress"
    assert by_title["Passed"].state == "passed"
    assert by_title["Failed"].state == "failed"


def test_outstanding_modules_come_first(db, make_module, make_user, owner):
    trainee = make_user(email="t@example.com", role="trainee")

    passing = make_module("Zebra passed")
    failing = make_module("Apple failed")
    for module in (passing, failing):
        _enrol(db, owner, module, role="instructor")
        _enrol(db, trainee, module)

    live, questions = _build_test(db, owner, passing)
    _sit(db, trainee, live.id, questions, right=2)
    live, questions = _build_test(db, owner, failing)
    _sit(db, trainee, live.id, questions, right=0)

    rows = results_service.for_person(db, trainee)
    assert [row.state for row in rows] == ["failed", "passed"]


def test_an_in_progress_module_links_into_the_attempt(db, make_module, make_user, owner):
    """Not to a review of something unfinished (FR-011)."""
    trainee = make_user(email="t@example.com", role="trainee")
    module = make_module("Phishing")
    _enrol(db, owner, module, role="instructor")
    _enrol(db, trainee, module)

    live, _ = _build_test(db, owner, module)
    row = attempt_service.start(db, trainee, live.id)

    result = results_service.for_person(db, trainee)[0]
    assert result.link == f"/attempts/{row.id}"


def test_a_removed_registration_disappears(db, make_module, make_user, owner):
    from app.services import registration_service

    trainee = make_user(email="t@example.com", role="trainee")
    admin = make_user(email="admin@example.com", role="administrator")
    module = make_module("Phishing")
    _enrol(db, trainee, module)

    assert len(results_service.for_person(db, trainee)) == 1

    registration_service.remove(db, admin, module.id, trainee.id)
    assert results_service.for_person(db, trainee) == []


def test_an_overridden_score_is_the_score_shown(db, make_module, make_user, owner):
    trainee = make_user(email="t@example.com", role="trainee")
    module = make_module("Phishing")
    _enrol(db, owner, module, role="instructor")
    _enrol(db, trainee, module)

    live, questions = _build_test(db, owner, module)
    attempt = _sit(db, trainee, live.id, questions, right=0)
    attempt_service.override_score(db, owner, attempt.id, ScoreOverride(score_percent=95))

    row = results_service.for_person(db, trainee)[0]
    assert row.score_percent == 95
    assert row.state == "passed"


# ------------------------------------------------------------- replaced tests


def test_publishing_a_replacement_resets_everyone(db, make_module, make_user, owner):
    trainee = make_user(email="t@example.com", role="trainee")
    module = make_module("Phishing")
    _enrol(db, owner, module, role="instructor")
    _enrol(db, trainee, module)

    first, questions = _build_test(db, owner, module, title="Original")
    _sit(db, trainee, first.id, questions, right=2)
    assert results_service.for_person(db, trainee)[0].state == "passed"

    _build_test(db, owner, module, title="Replacement")

    assert results_service.for_person(db, trainee)[0].state == "not started"


def test_the_old_attempts_stay_in_the_history(db, make_module, make_user, owner):
    """They no longer decide the state; they are still visible (FR-008)."""
    trainee = make_user(email="t@example.com", role="trainee")
    module = make_module("Phishing")
    _enrol(db, owner, module, role="instructor")
    _enrol(db, trainee, module)

    first, questions = _build_test(db, owner, module, title="Original")
    _sit(db, trainee, first.id, questions, right=2)
    _build_test(db, owner, module, title="Replacement")

    history = results_service.history_for(db, trainee, module.id, trainee)
    assert len(history) == 1
    assert history[0].test_title == "Original"
    assert history[0].at_replaced_test is True


def test_the_count_warned_about_is_the_number_that_changes(db, make_module, make_user, owner):
    module = make_module("Phishing")
    _enrol(db, owner, module, role="instructor")

    live, questions = _build_test(db, owner, module, title="Original")

    passers = []
    for n in range(3):
        person = make_user(email=f"p{n}@example.com", role="trainee")
        _enrol(db, person, module)
        _sit(db, person, live.id, questions, right=2)
        passers.append(person)

    failer = make_user(email="f@example.com", role="trainee")
    _enrol(db, failer, module)
    _sit(db, failer, live.id, questions, right=0)

    # Three passed, one failed. Only the passers lose something.
    assert results_service.count_affected_by_replacement(db, module.id) == 3


def test_nothing_to_warn_about_when_there_is_no_test(db, make_module):
    module = make_module("Phishing")
    assert results_service.count_affected_by_replacement(db, module.id) == 0


# ---------------------------------------------------------- the module history


def test_the_history_lists_every_attempt_newest_first(db, make_module, make_user, owner):
    trainee = make_user(email="t@example.com", role="trainee")
    module = make_module("Phishing")
    _enrol(db, owner, module, role="instructor")
    _enrol(db, trainee, module)

    live, questions = _build_test(db, owner, module)
    for right in (0, 1, 2):
        _sit(db, trainee, live.id, questions, right=right)

    history = results_service.history_for(db, trainee, module.id, trainee)
    assert len(history) == 3
    assert [row.attempt_number for row in history] == [3, 2, 1]


def test_a_module_with_no_attempts_returns_nothing_rather_than_failing(
    db, make_module, make_user, owner
):
    trainee = make_user(email="t@example.com", role="trainee")
    module = make_module("Phishing")
    _enrol(db, owner, module, role="instructor")
    _enrol(db, trainee, module)
    _build_test(db, owner, module)

    assert results_service.history_for(db, trainee, module.id, trainee) == []


def test_an_instructor_may_read_another_persons_history_on_their_module(
    db, make_module, make_user, owner
):
    trainee = make_user(email="t@example.com", role="trainee")
    module = make_module("Phishing")
    _enrol(db, owner, module, role="instructor")
    _enrol(db, trainee, module)

    live, questions = _build_test(db, owner, module)
    _sit(db, trainee, live.id, questions, right=1)

    history = results_service.history_for(db, trainee, module.id, owner)
    assert len(history) == 1


def test_an_instructor_elsewhere_may_not(db, make_module, make_user, owner):
    trainee = make_user(email="t@example.com", role="trainee")
    outsider = make_user(email="outsider@example.com", role="instructor")
    module = make_module("Phishing")
    _enrol(db, trainee, module)

    with pytest.raises(module_service.NotFound):
        results_service.history_for(db, trainee, module.id, outsider)


# ------------------------------------------------------- the instructor's view


def test_the_cohort_lists_trainees_with_their_state(db, make_module, make_user, owner):
    module = make_module("Phishing")
    _enrol(db, owner, module, role="instructor")

    live, questions = _build_test(db, owner, module)

    passer = make_user(email="pass@example.com", full_name="Ann Passer", role="trainee")
    failer = make_user(email="fail@example.com", full_name="Bob Failer", role="trainee")
    idle = make_user(email="idle@example.com", full_name="Cy Idle", role="trainee")
    for person in (passer, failer, idle):
        _enrol(db, person, module)

    _sit(db, passer, live.id, questions, right=2)
    _sit(db, failer, live.id, questions, right=0)

    rows = results_service.for_module(db, module.id, owner)

    assert len(rows) == 3
    assert rows[0].state == "failed", "those who have not passed come first"
    assert rows[-1].state == "passed"


def test_the_cohort_excludes_instructors(db, make_module, make_user, owner):
    module = make_module("Phishing")
    _enrol(db, owner, module, role="instructor")
    trainee = make_user(email="t@example.com", role="trainee")
    _enrol(db, trainee, module)

    rows = results_service.for_module(db, module.id, owner)
    assert [row.user_id for row in rows] == [trainee.id]


def test_a_trainee_may_not_see_the_cohort(db, make_module, make_user, owner):
    module = make_module("Phishing")
    trainee = make_user(email="t@example.com", role="trainee")
    _enrol(db, trainee, module)

    with pytest.raises(module_service.NotPermitted):
        results_service.for_module(db, module.id, trainee)


def test_an_instructor_elsewhere_is_refused_the_cohort(db, make_module, make_user):
    module = make_module("Phishing")
    outsider = make_user(email="outsider@example.com", role="instructor")

    with pytest.raises(module_service.NotFound):
        results_service.for_module(db, module.id, outsider)


def test_a_cohort_row_links_to_that_persons_history(db, make_module, make_user, owner):
    module = make_module("Phishing")
    _enrol(db, owner, module, role="instructor")
    trainee = make_user(email="t@example.com", role="trainee")
    _enrol(db, trainee, module)

    row = results_service.for_module(db, module.id, owner)[0]
    assert row.link == f"/modules/{module.id}/results/{trainee.id}"


def test_somebody_not_on_the_module_is_not_a_subject(db, make_module, make_user, owner):
    module = make_module("Phishing")
    _enrol(db, owner, module, role="instructor")
    stranger = make_user(email="stranger@example.com", role="trainee")

    assert results_service.subject_on_module(db, module.id, stranger.id) is None


# ------------------------------------------------------------ the phase's claim


def test_this_phase_adds_no_table(engine):
    """Its headline claim: everything on these pages is derived (FR-025, SC-010).

    Phase 4 added `notification`, which is a record of what somebody was told
    and not a results table: no figure on any results page reads it. The
    assertion is written as "the twelve, and nothing but the one Phase 4 named"
    so that a summary or cache table appearing later still fails here.
    """
    from sqlalchemy import inspect

    tables = set(inspect(engine).get_table_names())
    through_phase_three = {
        "user", "session",
        "module", "page", "content_image", "registration",
        "question", "answer_option", "test", "test_question",
        "attempt", "attempt_answer",
    }

    assert tables - through_phase_three == {"notification"}, (
        "Phase 3 adds no table of its own, and Phase 4 adds exactly one"
    )
