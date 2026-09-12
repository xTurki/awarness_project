"""Assigning a capacity through the roster form.

This file exists because the requirement had a model, a validated schema, and a
service that all supported it, and no way to reach any of them: the form had no
role field and the route never read one, so every person added became a trainee
(FR-004, FR-005, FR-024).
"""

from __future__ import annotations

import pytest
from sqlmodel import select

from app.models.module import Module
from app.models.registration import Registration


@pytest.fixture()
def module(db):
    row = Module(title="Phishing Awareness", is_published=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture()
def admin(make_user):
    return make_user(email="admin@example.com", role="administrator")


@pytest.fixture()
def owner(db, make_user, module):
    person = make_user(email="owner@example.com", role="instructor")
    db.add(
        Registration(user_id=person.id, module_id=module.id, role_in_module="instructor")
    )
    db.commit()
    return person


def _capacity(db, module_id, user_id):
    row = db.exec(
        select(Registration).where(
            Registration.module_id == module_id, Registration.user_id == user_id
        )
    ).first()
    return row.role_in_module if row else None


# ------------------------------------------------------------------- the form


def test_an_administrator_is_offered_the_choice(client, sign_in, admin, module, make_user):
    make_user(email="candidate@example.com", role="instructor")
    sign_in(admin)

    page = client.get(f"/modules/{module.id}/roster")

    assert page.status_code == 200
    assert 'name="role_in_module"' in page.text
    assert 'value="instructor"' in page.text


def test_an_instructor_is_not_offered_it(client, sign_in, owner, module, make_user):
    """Absent rather than shown and refused: a control nobody may use is not a
    control (FR-005)."""
    make_user(email="candidate@example.com", role="instructor")
    sign_in(owner)

    page = client.get(f"/modules/{module.id}/roster")

    assert page.status_code == 200
    assert 'name="role_in_module"' not in page.text


# --------------------------------------------------------------- the posting


def test_an_administrator_registers_somebody_as_an_instructor(
    client, db, sign_in, csrf, admin, module, make_user
):
    person = make_user(email="iris@example.com", role="instructor")
    sign_in(admin)

    token = csrf(f"/modules/{module.id}/roster")
    response = client.post(
        f"/modules/{module.id}/roster",
        data={
            "user_ids": [person.id],
            "role_in_module": "instructor",
            "csrf_token": token,
        },
    )

    assert response.status_code == 303
    assert _capacity(db, module.id, person.id) == "instructor"


def test_the_default_is_still_a_trainee(
    client, db, sign_in, csrf, admin, module, make_user
):
    person = make_user(email="t@example.com", role="trainee")
    sign_in(admin)

    token = csrf(f"/modules/{module.id}/roster")
    client.post(
        f"/modules/{module.id}/roster",
        data={"user_ids": [person.id], "csrf_token": token},
    )

    assert _capacity(db, module.id, person.id) == "trainee"


def test_an_instructor_posting_the_field_by_hand_is_refused(
    client, db, sign_in, csrf, owner, module, make_user
):
    """The field is absent from their page, so reaching this needs a crafted
    request. It is refused in the service, not by the template hiding it."""
    person = make_user(email="other@example.com", role="instructor")
    sign_in(owner)

    token = csrf(f"/modules/{module.id}/roster")
    response = client.post(
        f"/modules/{module.id}/roster",
        data={
            "user_ids": [person.id],
            "role_in_module": "instructor",
            "csrf_token": token,
        },
    )

    assert response.status_code == 403
    assert _capacity(db, module.id, person.id) is None


def test_the_roster_shows_each_persons_capacity(
    client, db, sign_in, admin, module, make_user
):
    """FR-029: everyone on it, and in what capacity."""
    iris = make_user(email="iris@example.com", full_name="Iris Instructor")
    tess = make_user(email="tess@example.com", full_name="Tess Trainee")
    db.add(Registration(user_id=iris.id, module_id=module.id, role_in_module="instructor"))
    db.add(Registration(user_id=tess.id, module_id=module.id, role_in_module="trainee"))
    db.commit()
    sign_in(admin)

    page = client.get(f"/modules/{module.id}/roster")

    assert "Iris Instructor" in page.text
    assert "Tess Trainee" in page.text
    assert "instructor" in page.text
    assert "trainee" in page.text
