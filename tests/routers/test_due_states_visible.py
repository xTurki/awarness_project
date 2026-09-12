"""The two new states, on all three pages Phase 3's states appear on.

This is the task that stops `due` and `overdue` existing in a function and on no
screen. All three pages read the same state function, each passing in a date
computed at the call site, so if one of them stopped passing a date the state
would silently revert to *passed* there and nowhere else (FR-010).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.database import utcnow
from app.models.attempt import Attempt
from app.models.module import Module
from app.models.registration import Registration
from app.schemas.quiz import QuestionWrite, TestWrite
from app.services import question_service, test_service

INTERVAL = 90


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
def recurring_test(db, owner, module):
    questions = [
        question_service.create_question(
            db, owner, module.id,
            QuestionWrite(prompt=f"Q{n}?", points=1, options=["a", "b"], correct=[0]),
        )
        for n in (1, 2)
    ]
    created = test_service.create(
        db, owner, module.id,
        TestWrite(
            title="Annual check",
            allowed_attempts=1,
            passing_score=80,
            retake_interval_days=INTERVAL,
            question_ids=[q.id for q in questions],
        ),
    )
    test_service.set_published(db, owner, created.id, True)
    return created


@pytest.fixture()
def lapsed(db, make_user, module, recurring_test):
    """Somebody who passed long enough ago to have lost currency."""
    person = make_user(email="t@example.com", full_name="Tess Trainee")
    db.add(
        Registration(
            user_id=person.id,
            module_id=module.id,
            role_in_module="trainee",
            registered_at=utcnow() - timedelta(days=400),
        )
    )
    passed_at = utcnow() - timedelta(days=INTERVAL + 10)
    db.add(
        Attempt(
            test_id=recurring_test.id,
            user_id=person.id,
            attempt_number=1,
            started_at=passed_at,
            ends_at=passed_at + timedelta(hours=1),
            submitted_at=passed_at,
            is_submitted=True,
            question_order=[],
            score_percent=90,
            passed=True,
        )
    )
    db.commit()
    return person


@pytest.fixture()
def approaching(db, make_user, module, recurring_test):
    """Somebody inside the warning period but not yet past it."""
    person = make_user(email="soon@example.com", full_name="Sam Soon")
    db.add(
        Registration(
            user_id=person.id,
            module_id=module.id,
            role_in_module="trainee",
            registered_at=utcnow() - timedelta(days=400),
        )
    )
    passed_at = utcnow() - timedelta(days=INTERVAL - 7)
    db.add(
        Attempt(
            test_id=recurring_test.id,
            user_id=person.id,
            attempt_number=1,
            started_at=passed_at,
            ends_at=passed_at + timedelta(hours=1),
            submitted_at=passed_at,
            is_submitted=True,
            question_order=[],
            score_percent=90,
            passed=True,
        )
    )
    db.commit()
    return person


# --------------------------------------------------- 1, the trainee dashboard


def test_overdue_shows_on_the_trainee_dashboard(client, sign_in, lapsed):
    sign_in(lapsed)
    page = client.get("/")

    assert "Overdue" in page.text
    assert "Passed" not in page.text, "a lapsed pass is not a pass"


def test_due_shows_on_the_trainee_dashboard(client, sign_in, approaching):
    sign_in(approaching)
    page = client.get("/")

    assert ">Due<" in page.text.replace(" ", "")


def test_overdue_sorts_to_the_top(client, db, sign_in, lapsed, make_user):
    """Outstanding things first, and nothing is more outstanding than something
    already missed (FR-010 with Phase 3 FR-007)."""
    settled = Module(title="Already Done", is_published=True)
    db.add(settled)
    db.commit()
    db.refresh(settled)
    db.add(
        Registration(user_id=lapsed.id, module_id=settled.id, role_in_module="trainee")
    )
    db.commit()

    sign_in(lapsed)
    page = client.get("/")

    assert page.text.index("Phishing Awareness") < page.text.index("Already Done")


# ------------------------------------------------- 2, the instructor's cohort


def test_overdue_shows_on_the_cohort_view(client, sign_in, owner, module, lapsed):
    sign_in(owner)
    page = client.get(f"/modules/{module.id}/results")

    assert page.status_code == 200
    assert "Tess Trainee" in page.text
    assert "Overdue" in page.text


def test_due_shows_on_the_cohort_view(client, sign_in, owner, module, approaching):
    sign_in(owner)
    page = client.get(f"/modules/{module.id}/results")

    assert "Sam Soon" in page.text
    assert ">Due<" in page.text.replace(" ", "")


# ---------------------------------------------------- 3, the module home page


def test_overdue_shows_on_the_module_home_page(client, sign_in, module, lapsed):
    """The badge Phase 3 added to a page that already existed, not a list of
    its own."""
    sign_in(lapsed)
    page = client.get(f"/modules/{module.id}")

    assert page.status_code == 200
    assert "Overdue" in page.text


def test_the_word_travels_with_the_colour(client, sign_in, lapsed):
    """Legible in greyscale, printed, or screenshotted: never colour alone
    (Phase 3 research R5)."""
    sign_in(lapsed)
    page = client.get("/")

    assert "text-bg-danger" in page.text
    assert "Overdue" in page.text


# ------------------------------------------------------------- and the terms


def test_a_trainee_is_shown_the_retake_interval(
    client, sign_in, module, recurring_test, lapsed
):
    """Shown to the people registered on it, not only to whoever set it
    (FR-006)."""
    sign_in(lapsed)
    page = client.get(f"/modules/{module.id}/tests/{recurring_test.id}")

    assert page.status_code == 200
    assert f"every {INTERVAL} days" in page.text
    # And the limit that no longer applies is not quoted at them (FR-005).
    assert "as many as you need" in page.text
