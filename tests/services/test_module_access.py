"""The authorisation chokepoint.

Every module-scoped action in this phase and in Phases 2 to 4 resolves through
`get_for`, so this matrix is what proves FR-009, SC-006, and SC-007.
"""

from __future__ import annotations

import pytest

from app.models.module import Module
from app.models.registration import Registration
from app.services import module_service


@pytest.fixture()
def make_module(db):
    def _make(title="Phishing Awareness", published=False):
        row = Module(title=title, is_published=published)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    return _make


@pytest.fixture()
def enrol(db):
    def _enrol(user, module, role="trainee"):
        db.add(
            Registration(user_id=user.id, module_id=module.id, role_in_module=role)
        )
        db.commit()

    return _enrol


# ------------------------------------------------------------- administrators


def test_an_administrator_sees_every_module_in_any_state(db, make_module, make_user):
    admin = make_user(email="a@example.com", role="administrator")
    unpublished = make_module(published=False)
    published = make_module(title="Passwords", published=True)

    assert module_service.get_for(db, unpublished.id, admin).id == unpublished.id
    assert module_service.get_for(db, published.id, admin).id == published.id


def test_an_administrator_may_write_to_any_module(db, make_module, make_user):
    admin = make_user(email="a@example.com", role="administrator")
    module = make_module()
    assert module_service.get_for_write(db, module.id, admin).id == module.id


# ----------------------------------------------------------------- instructors


def test_an_assigned_instructor_sees_an_unpublished_module(db, make_module, make_user, enrol):
    instructor = make_user(email="i@example.com", role="instructor")
    module = make_module(published=False)
    enrol(instructor, module, "instructor")

    assert module_service.get_for(db, module.id, instructor).id == module.id
    assert module_service.get_for_write(db, module.id, instructor).id == module.id


def test_an_unassigned_instructor_cannot_see_it_at_all(db, make_module, make_user):
    """Not found, not forbidden: existence is not disclosed."""
    instructor = make_user(email="i@example.com", role="instructor")
    module = make_module(published=True)

    with pytest.raises(module_service.NotFound):
        module_service.get_for(db, module.id, instructor)


def test_an_instructor_registered_as_a_trainee_may_not_write(db, make_module, make_user, enrol):
    instructor = make_user(email="i@example.com", role="instructor")
    module = make_module(published=True)
    enrol(instructor, module, "trainee")

    assert module_service.get_for(db, module.id, instructor).id == module.id
    with pytest.raises(module_service.NotPermitted):
        module_service.get_for_write(db, module.id, instructor)


# -------------------------------------------------------------------- trainees


def test_a_registered_trainee_sees_a_published_module(db, make_module, make_user, enrol):
    trainee = make_user(email="t@example.com", role="trainee")
    module = make_module(published=True)
    enrol(trainee, module)

    assert module_service.get_for(db, module.id, trainee).id == module.id


def test_a_registered_trainee_cannot_see_an_unpublished_module(db, make_module, make_user, enrol):
    trainee = make_user(email="t@example.com", role="trainee")
    module = make_module(published=False)
    enrol(trainee, module)

    with pytest.raises(module_service.NotFound):
        module_service.get_for(db, module.id, trainee)


def test_an_unregistered_trainee_cannot_see_a_published_module(db, make_module, make_user):
    trainee = make_user(email="t@example.com", role="trainee")
    module = make_module(published=True)

    with pytest.raises(module_service.NotFound):
        module_service.get_for(db, module.id, trainee)


def test_a_trainee_may_never_write(db, make_module, make_user, enrol):
    trainee = make_user(email="t@example.com", role="trainee")
    module = make_module(published=True)
    enrol(trainee, module)

    with pytest.raises(module_service.NotPermitted):
        module_service.get_for_write(db, module.id, trainee)


# --------------------------------------------------------------- soft deletion


def test_a_soft_deleted_module_is_invisible_to_everyone(db, make_module, make_user, enrol):
    admin = make_user(email="a@example.com", role="administrator")
    instructor = make_user(email="i@example.com", role="instructor")
    module = make_module(published=True)
    enrol(instructor, module, "instructor")

    module_service.soft_delete(db, admin, module.id)

    for actor in (admin, instructor):
        with pytest.raises(module_service.NotFound):
            module_service.get_for(db, module.id, actor)


def test_removing_a_registration_removes_the_module_from_view(db, make_module, make_user, enrol):
    trainee = make_user(email="t@example.com", role="trainee")
    module = make_module(published=True)
    enrol(trainee, module)

    from app.services import registration_service

    admin = make_user(email="a@example.com", role="administrator")
    registration_service.remove(db, admin, module.id, trainee.id)

    with pytest.raises(module_service.NotFound):
        module_service.get_for(db, module.id, trainee)


# ------------------------------------------------------------------- listings


def test_the_list_differs_by_role(db, make_module, make_user, enrol):
    admin = make_user(email="a@example.com", role="administrator")
    instructor = make_user(email="i@example.com", role="instructor")
    trainee = make_user(email="t@example.com", role="trainee")

    mine = make_module(title="Assigned", published=False)
    theirs = make_module(title="Somebody else's", published=True)
    enrol(instructor, mine, "instructor")
    enrol(trainee, theirs)

    assert len(module_service.list_for(db, admin)) == 2
    assert [m.title for m in module_service.list_for(db, instructor)] == ["Assigned"]
    assert [m.title for m in module_service.list_for(db, trainee)] == ["Somebody else's"]


def test_a_trainee_does_not_see_an_unpublished_module_they_are_on(
    db, make_module, make_user, enrol
):
    trainee = make_user(email="t@example.com", role="trainee")
    module = make_module(published=False)
    enrol(trainee, module)

    assert module_service.list_for(db, trainee) == []
