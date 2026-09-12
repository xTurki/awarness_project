"""Who may reach what, over HTTP.

Also the one Phase 1 requirement this phase is asked to keep honest: reading a
module's pages is never a precondition for starting its test (FR-039).
"""

from __future__ import annotations

import pytest

from app.models.module import Module
from app.models.registration import Registration
from app.schemas.quiz import QuestionWrite, TestWrite
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
def live_test(db, owner, module):
    questions = [
        question_service.create_question(
            db, owner, module.id,
            QuestionWrite(prompt=f"Q{n}?", points=1, options=["right", "wrong"], correct=[0]),
        )
        for n in range(1, 4)
    ]
    created = test_service.create(
        db, owner, module.id,
        TestWrite(
            title="Awareness check",
            time_limit_minutes=20,
            allowed_attempts=1,
            passing_score=80,
            question_ids=[q.id for q in questions],
        ),
    )
    test_service.set_published(db, owner, created.id, True)
    return created


# ------------------------------------------------------------------- starting


def test_an_unregistered_trainee_is_refused_the_test(client, make_user, sign_in, live_test, csrf):
    sign_in(make_user(email="stranger@example.com", role="trainee"))

    response = client.post(
        f"/tests/{live_test.id}/attempts", data={"csrf_token": csrf("/")}
    )
    assert response.status_code == 404


def test_a_registered_trainee_starts_and_lands_on_the_attempt(
    client, sign_in, trainee, live_test, csrf
):
    sign_in(trainee)
    response = client.post(
        f"/tests/{live_test.id}/attempts", data={"csrf_token": csrf("/")}
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/attempts/")


def test_exhausting_the_attempts_is_refused_and_says_how_many(
    client, db, sign_in, trainee, live_test, csrf
):
    attempt_service.submit(db, attempt_service.start(db, trainee, live_test.id))
    sign_in(trainee)

    response = client.post(
        f"/tests/{live_test.id}/attempts", data={"csrf_token": csrf("/")}
    )
    assert response.status_code == 409
    assert "1" in response.text


def test_reading_the_pages_is_not_a_precondition_for_the_test(
    client, db, sign_in, trainee, live_test, csrf
):
    """Phase 1 FR-035 and this phase's FR-039: content and assessment are always
    both reachable, and nothing tracks which pages anyone opened."""
    sign_in(trainee)

    response = client.post(
        f"/tests/{live_test.id}/attempts", data={"csrf_token": csrf("/")}
    )
    assert response.status_code == 303, "a trainee who read nothing can still start"


# ------------------------------------------------------------- reaching others


def test_a_trainee_cannot_open_another_persons_attempt(
    client, db, make_user, sign_in, trainee, live_test
):
    row = attempt_service.start(db, trainee, live_test.id)
    sign_in(make_user(email="other@example.com", role="trainee"))

    assert client.get(f"/attempts/{row.id}").status_code == 404
    assert client.get(f"/attempts/{row.id}/review").status_code == 404


def test_no_route_names_a_person_for_their_attempts():
    """FR-032 holds because there is nothing to guard: no path takes a user id."""
    from app.main import app

    attempt_paths = {r.path for r in app.routes if "attempt" in r.path}
    assert not any("user" in path for path in attempt_paths), attempt_paths


def test_an_instructor_elsewhere_is_refused_the_cohort(client, make_user, sign_in, live_test):
    sign_in(make_user(email="outsider@example.com", role="instructor"))
    assert client.get(f"/tests/{live_test.id}/attempts").status_code == 404


def test_the_owner_sees_the_cohort(client, db, sign_in, owner, trainee, live_test):
    attempt_service.submit(db, attempt_service.start(db, trainee, live_test.id))
    sign_in(owner)

    response = client.get(f"/tests/{live_test.id}/attempts")
    assert response.status_code == 200
    assert "Test Person" in response.text or "t@example.com" in response.text


# ------------------------------------------------------------------ the review


def test_the_review_of_an_unfinished_attempt_returns_you_to_it(
    client, db, sign_in, trainee, live_test
):
    row = attempt_service.start(db, trainee, live_test.id)
    sign_in(trainee)

    response = client.get(f"/attempts/{row.id}/review")
    assert response.status_code == 303
    assert response.headers["location"] == f"/attempts/{row.id}"


def test_opening_a_submitted_attempt_shows_the_review(client, db, sign_in, trainee, live_test):
    row = attempt_service.start(db, trainee, live_test.id)
    attempt_service.submit(db, row)
    sign_in(trainee)

    response = client.get(f"/attempts/{row.id}")
    assert response.status_code == 303
    assert response.headers["location"].endswith("/review")


def test_a_trainee_taking_a_test_is_never_told_which_option_is_correct(
    client, db, sign_in, trainee, live_test
):
    """QuestionRead carries no is_correct. This is the page that proves it."""
    row = attempt_service.start(db, trainee, live_test.id)
    sign_in(trainee)

    page = client.get(f"/attempts/{row.id}")
    assert page.status_code == 200
    assert "is_correct" not in page.text
    assert "Correct answer" not in page.text
