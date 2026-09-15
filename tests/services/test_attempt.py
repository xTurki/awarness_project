"""The attempt: starting it, answering, submitting, and surviving an interruption.

Three tests here carry more weight than the rest:

- the deadline does not move when the instructor edits the time limit
- a resumed attempt keeps its answers and its question order
- an expired attempt is submitted on read, scored on what it holds
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.database import utcnow
from app.models.attempt import Attempt
from app.models.module import Module
from app.models.registration import Registration
from app.models.test import Test
from app.schemas.quiz import QuestionWrite, ScoreOverride, TestWrite
from app.services import attempt_service, question_service, test_service


@pytest.fixture()
def module(db):
    row = Module(title="Phishing Awareness", is_published=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture()
def owner(db, make_user, module):
    person = make_user(email="owner@example.com", role="instructor")
    db.add(Registration(user_id=person.id, module_id=module.id, role_in_module="instructor"))
    db.commit()
    return person


@pytest.fixture()
def trainee(db, make_user, module):
    person = make_user(email="t@example.com", role="trainee")
    db.add(Registration(user_id=person.id, module_id=module.id, role_in_module="trainee"))
    db.commit()
    return person


@pytest.fixture()
def bank(db, owner, module):
    """Three questions: two single-answer, one with two correct options."""
    return [
        question_service.create_question(
            db, owner, module.id,
            QuestionWrite(prompt="Q1?", points=1, options=["right", "wrong"], correct=[0]),
        ),
        question_service.create_question(
            db, owner, module.id,
            QuestionWrite(prompt="Q2?", points=1, options=["right", "wrong"], correct=[0]),
        ),
        question_service.create_question(
            db, owner, module.id,
            QuestionWrite(prompt="Q3?", points=2, options=["a", "b", "c"], correct=[0, 1]),
        ),
    ]


@pytest.fixture()
def live_test(db, owner, module, bank):
    created = test_service.create(
        db, owner, module.id,
        TestWrite(
            title="Awareness check",
            time_limit_minutes=20,
            allowed_attempts=2,
            passing_score=80,
            question_ids=[q.id for q in bank],
        ),
    )
    test_service.set_published(db, owner, created.id, True)
    return created


def _correct_ids(question):
    return [o.id for o in question.options if o.is_correct]


# ------------------------------------------------------------------- starting


def test_starting_fixes_the_deadline_and_the_order(db, trainee, live_test, bank):
    row = attempt_service.start(db, trainee, live_test.id)

    assert row.attempt_number == 1
    assert row.ends_at > row.started_at
    assert sorted(row.question_order) == sorted(q.id for q in bank)


def test_starting_again_resumes_the_open_attempt(db, trainee, live_test):
    """One attempt in progress per test. A second device continues the same one."""
    first = attempt_service.start(db, trainee, live_test.id)
    second = attempt_service.start(db, trainee, live_test.id)

    assert first.id == second.id


def test_an_unregistered_person_cannot_start(db, make_user, live_test):
    stranger = make_user(email="stranger@example.com", role="trainee")
    with pytest.raises(attempt_service.AttemptNotFound):
        attempt_service.start(db, stranger, live_test.id)


def test_an_unpublished_test_cannot_be_started(db, owner, trainee, live_test):
    test_service.set_published(db, owner, live_test.id, False)
    with pytest.raises(attempt_service.AttemptNotFound):
        attempt_service.start(db, trainee, live_test.id)


def test_a_test_that_has_closed_cannot_be_started(db, owner, trainee, live_test):
    row = db.get(Test, live_test.id)
    row.closes_at = utcnow() - timedelta(minutes=1)
    db.add(row)
    db.commit()

    with pytest.raises(attempt_service.OutsideWindow):
        attempt_service.start(db, trainee, live_test.id)


def test_attempts_are_limited_and_the_refusal_says_how_many(db, trainee, live_test):
    for _ in range(2):
        row = attempt_service.start(db, trainee, live_test.id)
        attempt_service.submit(db, row)

    with pytest.raises(attempt_service.NoAttemptsLeft) as caught:
        attempt_service.start(db, trainee, live_test.id)
    assert "2" in str(caught.value)


def test_the_attempt_number_is_derived_not_supplied(db, trainee, live_test):
    first = attempt_service.start(db, trainee, live_test.id)
    attempt_service.submit(db, first)
    second = attempt_service.start(db, trainee, live_test.id)

    assert (first.attempt_number, second.attempt_number) == (1, 2)


# ------------------------------------------------------------------ answering


def test_each_answer_is_its_own_write(db, trainee, live_test, bank):
    row = attempt_service.start(db, trainee, live_test.id)

    attempt_service.save_answer(db, trainee, row.id, bank[0].id, _correct_ids(bank[0]))
    assert attempt_service.answers_for(db, row.id) == {bank[0].id: _correct_ids(bank[0])}

    attempt_service.save_answer(db, trainee, row.id, bank[1].id, _correct_ids(bank[1]))
    assert len(attempt_service.answers_for(db, row.id)) == 2


def test_changing_an_answer_leaves_one_row(db, trainee, live_test, bank):
    row = attempt_service.start(db, trainee, live_test.id)
    wrong = [o.id for o in bank[0].options if not o.is_correct]

    for _ in range(5):
        attempt_service.save_answer(db, trainee, row.id, bank[0].id, wrong)
    attempt_service.save_answer(db, trainee, row.id, bank[0].id, _correct_ids(bank[0]))

    answers = attempt_service.answers_for(db, row.id)
    assert len(answers) == 1
    assert answers[bank[0].id] == _correct_ids(bank[0]), "the last write wins"


def test_an_answer_to_a_question_outside_the_attempt_is_refused(db, trainee, live_test):
    row = attempt_service.start(db, trainee, live_test.id)
    with pytest.raises(attempt_service.AttemptNotFound):
        attempt_service.save_answer(db, trainee, row.id, 999_999, [1])


def test_another_person_cannot_answer_into_your_attempt(db, make_user, trainee, live_test, bank):
    row = attempt_service.start(db, trainee, live_test.id)
    other = make_user(email="other@example.com", role="trainee")

    with pytest.raises(attempt_service.AttemptNotFound):
        attempt_service.save_answer(db, other, row.id, bank[0].id, [1])


# ------------------------------------------------------------------ submitting


def test_submitting_scores_it(db, trainee, live_test, bank):
    row = attempt_service.start(db, trainee, live_test.id)
    for question in bank:
        attempt_service.save_answer(db, trainee, row.id, question.id, _correct_ids(question))

    submitted = attempt_service.submit(db, row)

    assert submitted.is_submitted is True
    assert submitted.points_earned == 4
    assert submitted.points_possible == 4
    assert submitted.score_percent == 100
    assert submitted.passed is True


def test_a_partly_correct_multi_answer_earns_nothing(db, trainee, live_test, bank):
    row = attempt_service.start(db, trainee, live_test.id)
    attempt_service.save_answer(db, trainee, row.id, bank[0].id, _correct_ids(bank[0]))
    attempt_service.save_answer(db, trainee, row.id, bank[1].id, _correct_ids(bank[1]))
    # Only one of the two correct options on the multi-answer question.
    attempt_service.save_answer(db, trainee, row.id, bank[2].id, [_correct_ids(bank[2])[0]])

    submitted = attempt_service.submit(db, row)

    assert submitted.points_earned == 2, "no partial credit for the two-point question"
    assert submitted.score_percent == 50
    assert submitted.passed is False


def test_an_attempt_with_no_answers_submits_and_scores_zero(db, trainee, live_test):
    row = attempt_service.start(db, trainee, live_test.id)
    submitted = attempt_service.submit(db, row)

    assert submitted.is_submitted is True
    assert submitted.score_percent == 0
    assert submitted.passed is False


def test_submitting_twice_returns_the_same_result(db, trainee, live_test, bank):
    row = attempt_service.start(db, trainee, live_test.id)
    attempt_service.save_answer(db, trainee, row.id, bank[0].id, _correct_ids(bank[0]))

    first = attempt_service.submit(db, row)
    submitted_at = first.submitted_at
    score = first.score_percent

    second = attempt_service.submit(db, row)

    assert second.submitted_at == submitted_at
    assert second.score_percent == score


def test_answering_after_submission_is_refused(db, trainee, live_test, bank):
    row = attempt_service.start(db, trainee, live_test.id)
    attempt_service.submit(db, row)

    with pytest.raises(attempt_service.AttemptClosed):
        attempt_service.save_answer(db, trainee, row.id, bank[0].id, [1])


# ------------------------------------------------------- surviving an interruption


def test_a_resumed_attempt_keeps_every_answer(db, trainee, live_test, bank):
    row = attempt_service.start(db, trainee, live_test.id)
    attempt_service.save_answer(db, trainee, row.id, bank[0].id, _correct_ids(bank[0]))
    attempt_service.save_answer(db, trainee, row.id, bank[1].id, _correct_ids(bank[1]))

    # As if the browser died and came back.
    resumed = attempt_service.get_own(db, trainee, row.id)

    assert attempt_service.answers_for(db, resumed.id) == {
        bank[0].id: _correct_ids(bank[0]),
        bank[1].id: _correct_ids(bank[1]),
    }


def test_a_resumed_attempt_keeps_the_same_question_order(db, trainee, live_test):
    row = attempt_service.start(db, trainee, live_test.id)
    before = list(row.question_order)

    resumed = attempt_service.get_own(db, trainee, row.id)

    assert list(resumed.question_order) == before


def test_editing_the_time_limit_does_not_move_a_running_deadline(db, owner, trainee, live_test):
    """The test that proves `ends_at` is stored rather than recomputed (FR-016).

    If this fails, an instructor's edit reaches into an attempt somebody is
    sitting, which is the failure the whole design is shaped to prevent.
    """
    row = attempt_service.start(db, trainee, live_test.id)
    deadline = row.ends_at

    stored = db.get(Test, live_test.id)
    stored.time_limit_minutes = 60
    db.add(stored)
    db.commit()

    after = attempt_service.get_own(db, trainee, row.id)
    assert after.ends_at == deadline


def test_the_deadline_is_the_earlier_of_the_limit_and_the_closing_time(db, owner, trainee, module, bank):
    """The other branch of min(): the window closes before the time limit runs out."""
    created = test_service.create(
        db, owner, module.id,
        TestWrite(
            title="Closing soon",
            time_limit_minutes=20,
            closes_at=utcnow() + timedelta(minutes=5),
            allowed_attempts=1,
            question_ids=[q.id for q in bank],
        ),
    )
    test_service.set_published(db, owner, created.id, True)

    row = attempt_service.start(db, trainee, created.id)
    minutes = (row.ends_at - row.started_at).total_seconds() / 60

    assert 4 <= minutes <= 6, "the closing time wins over the twenty-minute limit"


# --------------------------------------------------------------- running out


def test_an_answer_after_the_deadline_is_refused(db, trainee, live_test, bank):
    row = attempt_service.start(db, trainee, live_test.id)
    row.ends_at = utcnow() - timedelta(seconds=1)
    db.add(row)
    db.commit()

    with pytest.raises(attempt_service.AttemptClosed):
        attempt_service.save_answer(db, trainee, row.id, bank[0].id, _correct_ids(bank[0]))


def test_an_expired_attempt_is_submitted_on_read_and_scored_on_what_it_holds(
    db, trainee, live_test, bank
):
    row = attempt_service.start(db, trainee, live_test.id)
    attempt_service.save_answer(db, trainee, row.id, bank[0].id, _correct_ids(bank[0]))

    row.ends_at = utcnow() - timedelta(seconds=1)
    db.add(row)
    db.commit()

    seen = attempt_service.get_own(db, trainee, row.id)

    assert seen.is_submitted is True
    assert seen.points_earned == 1, "scored on the one answer it held"
    assert seen.score_percent == 25


def test_an_abandoned_attempt_does_not_stay_open_forever(db, trainee, live_test):
    row = attempt_service.start(db, trainee, live_test.id)
    row.ends_at = utcnow() - timedelta(hours=1)
    db.add(row)
    db.commit()

    history = attempt_service.history_for(db, trainee, live_test.id)
    assert history[0].is_submitted is True


# ------------------------------------------------------------------ reviewing


def test_the_review_shows_the_answer_given_and_the_correct_one(db, trainee, live_test, bank):
    row = attempt_service.start(db, trainee, live_test.id)
    wrong = [o.id for o in bank[0].options if not o.is_correct]
    attempt_service.save_answer(db, trainee, row.id, bank[0].id, wrong)
    submitted = attempt_service.submit(db, row)

    lines = attempt_service.review(db, submitted)
    first = next(line for line in lines if line[0].id == bank[0].id)
    question, chosen, correct = first

    assert chosen == wrong
    assert correct is False
    assert any(o.is_correct for o in question.options), "the right answer travels with it"


def test_three_attempts_each_score_on_their_own_answers(db, trainee, live_test, bank):
    """Nothing carries over between attempts: an empty one scores nothing even
    after a perfect one.

    Which of the three then represents the person is decided by `state` and
    `due`, on the list rather than by a query, and is tested there."""
    scores = []
    for selection in ([], [q for q in bank], [bank[0], bank[1]]):
        row = attempt_service.start(db, trainee, live_test.id)
        for question in selection:
            attempt_service.save_answer(
                db, trainee, row.id, question.id, _correct_ids(question)
            )
        scores.append(attempt_service.submit(db, row).score_percent)
        stored = db.get(Test, live_test.id)
        stored.allowed_attempts += 1
        db.add(stored)
        db.commit()

    assert scores == [0, 100, 50]


def test_another_trainee_cannot_reach_your_attempt(db, make_user, trainee, live_test):
    row = attempt_service.start(db, trainee, live_test.id)
    other = make_user(email="other@example.com", role="trainee")

    with pytest.raises(attempt_service.AttemptNotFound):
        attempt_service.get_viewable(db, other, row.id)


def test_the_instructor_may_view_an_attempt_on_their_module(db, owner, trainee, live_test):
    row = attempt_service.start(db, trainee, live_test.id)
    assert attempt_service.get_viewable(db, owner, row.id).id == row.id


def test_an_instructor_elsewhere_may_not(db, make_user, trainee, live_test):
    outsider = make_user(email="outsider@example.com", role="instructor")
    row = attempt_service.start(db, trainee, live_test.id)

    with pytest.raises(attempt_service.AttemptNotFound):
        attempt_service.get_viewable(db, outsider, row.id)


# --------------------------------------------------------------- overriding


def test_an_override_replaces_the_score_and_the_outcome(db, owner, trainee, live_test):
    row = attempt_service.start(db, trainee, live_test.id)
    submitted = attempt_service.submit(db, row)
    assert submitted.passed is False

    corrected = attempt_service.override_score(
        db, owner, row.id, ScoreOverride(score_percent=90)
    )

    assert corrected.score_percent == 90
    assert corrected.passed is True, "pass or fail follows the new number"
    assert corrected.score_overridden is True


def test_an_override_on_an_unfinished_attempt_is_refused(db, owner, trainee, live_test):
    row = attempt_service.start(db, trainee, live_test.id)

    with pytest.raises(attempt_service.NotSubmitted):
        attempt_service.override_score(db, owner, row.id, ScoreOverride(score_percent=90))


def test_an_instructor_elsewhere_cannot_override(db, make_user, trainee, live_test):
    from app.services import module_service

    outsider = make_user(email="outsider@example.com", role="instructor")
    row = attempt_service.start(db, trainee, live_test.id)
    attempt_service.submit(db, row)

    with pytest.raises(module_service.NotFound):
        attempt_service.override_score(db, outsider, row.id, ScoreOverride(score_percent=90))


def test_the_trainee_sees_the_corrected_score(db, owner, trainee, live_test):
    row = attempt_service.start(db, trainee, live_test.id)
    attempt_service.submit(db, row)
    attempt_service.override_score(db, owner, row.id, ScoreOverride(score_percent=90))

    history = attempt_service.history_for(db, trainee, live_test.id)
    assert history[0].score_percent == 90
    assert history[0].score_overridden is True


def test_the_cohort_lists_everyone_who_attempted(db, owner, trainee, live_test, make_user, module):
    second = make_user(email="second@example.com", role="trainee")
    db.add(Registration(user_id=second.id, module_id=module.id, role_in_module="trainee"))
    db.commit()

    attempt_service.submit(db, attempt_service.start(db, trainee, live_test.id))
    attempt_service.submit(db, attempt_service.start(db, second, live_test.id))

    people = attempt_service.list_attempts_for_test(db, owner, live_test.id)
    assert len(people) == 2
    assert all(person.attempts for person in people)
