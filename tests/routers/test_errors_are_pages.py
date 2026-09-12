"""A refusal reaches a person as a page, never as JSON.

Before this, a rejected form showed the browser a line of
`{"detail": "A retake interval must be at least 14 days..."}`. The sentence was
right and the delivery was wrong: it tells somebody using the platform nothing,
looks like a crash, and loses everything they had typed.

Two separate fixes are covered here. Forms re-render themselves with the reason
above them, the way the sign-in page reports a wrong password. Everything else
falls through to an error page, so no refusal anywhere can arrive as JSON.
"""

from __future__ import annotations

import pytest

from app.models.module import Module
from app.models.registration import Registration
from app.schemas.quiz import QuestionWrite, TestWrite
from app.services import question_service, test_service


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
def a_test(db, owner, module):
    questions = [
        question_service.create_question(
            db, owner, module.id,
            QuestionWrite(prompt="Q?", points=1, options=["a", "b"], correct=[0]),
        )
    ]
    return test_service.create(
        db, owner, module.id,
        TestWrite(title="Check", allowed_attempts=1, passing_score=80,
                  question_ids=[q.id for q in questions]),
    )


def _save(client, csrf, module_id, test_id, **overrides):
    data = {
        "title": "Check",
        "instructions": "",
        "opens_at": "",
        "closes_at": "",
        "time_limit_minutes": "",
        "allowed_attempts": 1,
        "shuffle_questions": "",
        "passing_score": "80",
        "retake_interval_days": "",
        "completion_deadline_days": "",
        "csrf_token": csrf(f"/modules/{module_id}/tests/{test_id}/edit"),
    }
    data.update(overrides)
    return client.post(f"/modules/{module_id}/tests/{test_id}", data=data)


# ------------------------------------------------- the one that was reported


def test_a_short_retake_interval_comes_back_as_a_page(
    client, sign_in, owner, module, a_test, csrf
):
    """Seven days against a fourteen-day warning period: the warning would fire
    before the person had taken the test."""
    sign_in(owner)

    response = _save(client, csrf, module.id, a_test.id, retake_interval_days="7")

    assert response.status_code == 400
    assert "text/html" in response.headers["content-type"]
    assert '{"detail"' not in response.text


def test_the_reason_is_shown_above_the_form(
    client, sign_in, owner, module, a_test, csrf
):
    sign_in(owner)

    response = _save(client, csrf, module.id, a_test.id, retake_interval_days="7")

    assert 'class="alert' in response.text
    assert "at least 14 days" in response.text
    # And the form is still there to correct, not an error page to go back from.
    assert 'name="retake_interval_days"' in response.text


def test_what_was_typed_is_still_there(client, sign_in, owner, module, a_test, csrf):
    """Somebody who has just filled in eight fields should not have to fill them
    in again to read why one was refused."""
    sign_in(owner)

    response = _save(
        client, csrf, module.id, a_test.id,
        title="A Carefully Typed Title", retake_interval_days="7",
    )

    assert "A Carefully Typed Title" in response.text


def test_a_schedule_with_no_pass_mark_is_reported_the_same_way(
    client, sign_in, owner, module, a_test, csrf
):
    sign_in(owner)

    response = _save(
        client, csrf, module.id, a_test.id,
        passing_score="", retake_interval_days="90",
    )

    assert response.status_code == 400
    assert "pass mark" in response.text.lower()
    assert '{"detail"' not in response.text


def test_a_valid_schedule_still_saves(client, sign_in, owner, module, a_test, csrf):
    sign_in(owner)

    response = _save(client, csrf, module.id, a_test.id, retake_interval_days="90")

    assert response.status_code == 303


# ------------------------------------------------- everything else is a page


@pytest.mark.parametrize(
    "path,expected",
    [
        ("/modules/999999", 404),
        ("/modules/999999/tests", 404),
        ("/admin/accounts", 403),
    ],
)
def test_a_refusal_renders_as_html(client, sign_in, make_user, path, expected):
    sign_in(make_user(email="t@example.com", role="trainee"))

    response = client.get(path)

    assert response.status_code == expected
    assert "text/html" in response.headers["content-type"]
    assert '{"detail"' not in response.text


def test_the_error_page_says_what_happened_in_plain_words(
    client, sign_in, make_user
):
    sign_in(make_user(email="t@example.com", role="trainee"))

    response = client.get("/admin/accounts")

    assert "You do not have access to this" in response.text
    assert "Back to the dashboard" in response.text


def test_a_missing_page_is_named_as_such(client, sign_in, make_user):
    sign_in(make_user(email="t@example.com", role="trainee"))

    response = client.get("/modules/999999")

    assert "Not found" in response.text


# ------------------------------------------------------ redirects still work


def test_a_guard_redirect_is_not_rendered_as_a_failure(client):
    """The route guards raise redirects as exceptions too. Treating a 303 as a
    refusal would break every sign-in on the platform."""
    response = client.get("/modules")

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_the_password_gate_still_redirects(client, sign_in, make_user):
    sign_in(make_user(email="new@example.com", must_set_password=True))

    response = client.get("/modules")

    assert response.status_code == 303
    assert response.headers["location"] == "/password/new"
