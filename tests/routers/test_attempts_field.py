"""The attempts field on the test form: a number, or Unlimited."""

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
    db.add(Registration(user_id=person.id, module_id=module.id, role_in_module="instructor"))
    db.commit()
    return person


@pytest.fixture()
def a_test(db, owner, module):
    question = question_service.create_question(
        db, owner, module.id,
        QuestionWrite(prompt="Q?", points=1, options=["a", "b"], correct=[0]),
    )
    return test_service.create(
        db, owner, module.id,
        TestWrite(title="Check", allowed_attempts=1, passing_score=80, question_ids=[question.id]),
    )


def _save(client, csrf, module_id, test_id, **overrides):
    data = {
        "title": "Check", "instructions": "", "opens_at": "", "closes_at": "",
        "time_limit_minutes": "", "allowed_attempts": "1", "shuffle_questions": "",
        "passing_score": "80", "retake_interval_days": "", "completion_deadline_days": "",
        "question_count": "1",
        "csrf_token": csrf(f"/modules/{module_id}/tests/{test_id}/edit"),
    }
    data.update(overrides)
    return client.post(f"/modules/{module_id}/tests/{test_id}", data=data)


def test_a_typed_number_is_stored(client, db, sign_in, csrf, owner, module, a_test):
    sign_in(owner)
    assert _save(client, csrf, module.id, a_test.id, allowed_attempts="5").status_code == 303
    assert test_service.row_of(db, a_test.id).allowed_attempts == 5


def test_ticking_unlimited_stores_unlimited(client, db, sign_in, csrf, owner, module, a_test):
    sign_in(owner)
    response = _save(client, csrf, module.id, a_test.id, unlimited_attempts="true")

    assert response.status_code == 303
    assert test_service.row_of(db, a_test.id).allowed_attempts == 0
    page = client.get(f"/modules/{module.id}/tests/{a_test.id}")
    assert "Unlimited" in page.text


def test_the_edit_form_shows_unlimited_ticked(client, db, sign_in, csrf, owner, module, a_test):
    sign_in(owner)
    _save(client, csrf, module.id, a_test.id, unlimited_attempts="true")

    form = client.get(f"/modules/{module.id}/tests/{a_test.id}/edit").text
    tag = form[form.index('id="unlimited_attempts"') - 120: form.index('id="unlimited_attempts"') + 160]
    assert "checked" in tag


@pytest.mark.parametrize("typed", ["", "0", "abc"])
def test_no_number_and_no_tick_is_refused_with_a_reason(
    client, sign_in, csrf, owner, module, a_test, typed
):
    sign_in(owner)
    response = _save(client, csrf, module.id, a_test.id, allowed_attempts=typed)

    assert response.status_code == 400
    assert "tick Unlimited attempts" in response.text
