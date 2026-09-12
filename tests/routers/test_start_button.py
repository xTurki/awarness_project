"""The Start button appears only for somebody who can actually start.

Reported from a real session: an administrator published a test, pressed Start,
and got a page saying "Not found". The refusal was right, because they were not
registered on the module, but the page had offered them the button and then
answered with the least helpful sentence available.

The last test in this file is the one that keeps it honest: whatever the page
decides, the service must agree.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.database import utcnow
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
    db.add(Registration(user_id=person.id, module_id=module.id,
                        role_in_module="instructor"))
    db.commit()
    return person


@pytest.fixture()
def live_test(db, owner, module):
    questions = [
        question_service.create_question(
            db, owner, module.id,
            QuestionWrite(prompt="Q?", points=1, options=["a", "b"], correct=[0]),
        )
    ]
    created = test_service.create(
        db, owner, module.id,
        TestWrite(title="Check", allowed_attempts=1, passing_score=80,
                  question_ids=[q.id for q in questions]),
    )
    test_service.set_published(db, owner, created.id, True)
    return created


@pytest.fixture()
def trainee(db, make_user, module):
    person = make_user(email="t@example.com", role="trainee")
    db.add(Registration(user_id=person.id, module_id=module.id,
                        role_in_module="trainee"))
    db.commit()
    return person


def _window(db, test_id, opens=None, closes=None):
    """The column is a DATETIME, so it keeps whole seconds and nothing finer.

    Dropping the microseconds here is what the database does anyway; keeping
    them would mean comparing a value against a truncated copy of itself.
    """
    from app.models.test import Test

    row = db.get(Test, test_id)
    row.opens_at = opens.replace(microsecond=0) if opens else None
    row.closes_at = closes.replace(microsecond=0) if closes else None
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


# ------------------------------------------------------- the reported case


def test_somebody_not_registered_is_not_offered_the_button(
    client, sign_in, make_user, module, live_test
):
    """An administrator can see the test. They still cannot sit it."""
    sign_in(make_user(email="admin@example.com", role="administrator"))

    page = client.get(f"/modules/{module.id}/tests/{live_test.id}")

    assert page.status_code == 200
    assert "Cannot start" in page.text
    assert f'action="/tests/{live_test.id}/attempts"' not in page.text


def test_and_is_told_why_in_words_they_can_act_on(
    client, sign_in, make_user, module, live_test
):
    sign_in(make_user(email="admin@example.com", role="administrator"))

    page = client.get(f"/modules/{module.id}/tests/{live_test.id}")

    assert "not registered on this module" in page.text
    assert "Ask whoever runs it to add you" in page.text
    # Not the sentence that started this.
    assert "Not found" not in page.text


# ------------------------------------------------------------- the window


def test_a_closed_test_says_when_it_closed(client, db, sign_in, trainee, module, live_test):
    _window(db, live_test.id, closes=utcnow() - timedelta(hours=1))
    sign_in(trainee)

    page = client.get(f"/modules/{module.id}/tests/{live_test.id}")

    assert "Cannot start" in page.text
    assert "This test closed at" in page.text


def test_a_test_not_open_yet_says_when_it_opens(
    client, db, sign_in, trainee, module, live_test
):
    _window(db, live_test.id, opens=utcnow() + timedelta(days=1))
    sign_in(trainee)

    page = client.get(f"/modules/{module.id}/tests/{live_test.id}")

    assert "This test opens at" in page.text


def test_the_window_is_among_the_terms_before_anybody_presses_anything(
    client, db, sign_in, trainee, module, live_test
):
    """It belongs with the time limit and the pass mark, not as a refusal after
    the fact."""
    _window(db, live_test.id, opens=utcnow() - timedelta(hours=1),
            closes=utcnow() + timedelta(hours=1))
    sign_in(trainee)

    page = client.get(f"/modules/{module.id}/tests/{live_test.id}")

    assert "Open:" in page.text
    assert "until" in page.text


# ---------------------------------------------------------- who does get it


def test_a_registered_trainee_gets_the_button(client, sign_in, trainee, module, live_test):
    sign_in(trainee)

    page = client.get(f"/modules/{module.id}/tests/{live_test.id}")

    assert f'action="/tests/{live_test.id}/attempts"' in page.text
    assert "Cannot start" not in page.text


def test_an_exhausted_limit_is_named_rather_than_discovered(
    client, db, sign_in, trainee, module, live_test
):
    attempt = attempt_service.start(db, trainee, live_test.id)
    attempt_service.submit_own(db, trainee, attempt.id)
    sign_in(trainee)

    page = client.get(f"/modules/{module.id}/tests/{live_test.id}")

    assert "used all 1 permitted attempts" in page.text


def test_an_open_attempt_can_be_resumed_even_past_the_window(
    client, db, sign_in, trainee, module, live_test
):
    """The window governs when an attempt may start. Theirs already did."""
    attempt_service.start(db, trainee, live_test.id)
    _window(db, live_test.id, closes=utcnow() + timedelta(seconds=5))
    sign_in(trainee)

    page = client.get(f"/modules/{module.id}/tests/{live_test.id}")

    assert "Resume your attempt" in page.text


# ------------------------------------------- the page and the service agree


@pytest.mark.parametrize(
    "arrange",
    [
        "registered",
        "not_registered",
        "closed",
        "not_open_yet",
        "unpublished",
        "limit_used",
    ],
)
def test_whatever_the_page_decides_the_service_agrees(
    db, make_user, module, live_test, trainee, owner, arrange
):
    """The page offering a button the service refuses is the whole bug. This
    walks every reason and asserts the two never disagree."""
    actor = trainee

    if arrange == "not_registered":
        actor = make_user(email="stranger@example.com", role="administrator")
    elif arrange == "closed":
        _window(db, live_test.id, closes=utcnow() - timedelta(hours=1))
    elif arrange == "not_open_yet":
        _window(db, live_test.id, opens=utcnow() + timedelta(days=1))
    elif arrange == "unpublished":
        test_service.set_published(db, owner, live_test.id, False)
    elif arrange == "limit_used":
        attempt = attempt_service.start(db, trainee, live_test.id)
        attempt_service.submit_own(db, trainee, attempt.id)

    row = test_service.row_of(db, live_test.id)
    reason = attempt_service.why_not_startable(db, actor, row)

    if reason is None:
        started = attempt_service.start(db, actor, live_test.id)
        assert started is not None
    else:
        with pytest.raises(
            (
                attempt_service.AttemptNotFound,
                attempt_service.OutsideWindow,
                attempt_service.NoAttemptsLeft,
            )
        ):
            attempt_service.start(db, actor, live_test.id)


# ------------------------------------------------- times reach the reader's zone


def test_the_window_carries_the_moment_for_the_browser_to_localise(
    client, db, sign_in, trainee, module, live_test
):
    """Reported from Sydney: an instructor typed 05:25 meaning their own clock,
    it was stored as 05:25 UTC, and the test opened ten hours late.

    The stored moment is naive UTC, which is right. What was missing is the
    conversion at the edges, and only the browser knows the reader's zone.
    """
    row = _window(db, live_test.id, opens=utcnow() + timedelta(days=1))
    sign_in(trainee)

    page = client.get(f"/modules/{module.id}/tests/{live_test.id}")

    assert f'data-utc="{row.opens_at.isoformat()}"' in page.text
    # And it still reads correctly with no JavaScript at all, marked UTC.
    assert "UTC" in page.text


def test_the_date_fields_carry_it_too(client, db, sign_in, owner, module, live_test):
    row = _window(db, live_test.id, opens=utcnow() + timedelta(days=1))
    sign_in(owner)

    page = client.get(f"/modules/{module.id}/tests/{live_test.id}/edit")

    assert f'data-utc="{row.opens_at.isoformat()}"' in page.text
    # The plain value stays UTC, so the field works unchanged without the script.
    assert row.opens_at.strftime("%Y-%m-%dT%H:%M") in page.text


def test_the_form_says_whose_clock_it_is_speaking_in(
    client, sign_in, owner, module, live_test
):
    sign_in(owner)
    page = client.get(f"/modules/{module.id}/tests/{live_test.id}/edit")

    assert "data-timezone" in page.text
    assert "your own time zone" in page.text


def test_the_script_ships_with_every_page(client, sign_in, trainee):
    sign_in(trainee)
    page = client.get("/")

    assert "/static/js/localtime.js" in page.text


def test_the_script_is_versioned_like_the_stylesheet(client, sign_in, trainee):
    """Otherwise a change to it is served stale for four hours, which is the
    bug the asset digest already exists to prevent."""
    sign_in(trainee)
    page = client.get("/")

    assert "/static/js/localtime.js?v=" in page.text
