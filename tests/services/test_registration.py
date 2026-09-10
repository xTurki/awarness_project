"""Registration: several at once, no duplicates, and removal.

The unique constraint is what makes "no duplicates" a database guarantee rather
than a check somebody could forget (FR-025, FR-027).
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.module import Module
from app.models.registration import Registration
from app.schemas.module import RosterAdd
from app.services import module_service, registration_service


@pytest.fixture()
def module(db):
    row = Module(title="Phishing Awareness", is_published=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture()
def admin(make_user):
    return make_user(email="a@example.com", role="administrator")


@pytest.fixture()
def five(make_user):
    return [
        make_user(email=f"t{n}@example.com", full_name=f"Trainee {n}", role="trainee")
        for n in range(1, 6)
    ]


def test_five_people_are_registered_in_one_action(db, admin, module, five):
    added = registration_service.register_many(
        db, admin, module.id, RosterAdd(user_ids=[p.id for p in five])
    )

    assert added == 5
    assert len(registration_service.roster(db, admin, module.id)) == 5


def test_all_five_then_see_the_module(db, admin, module, five):
    registration_service.register_many(
        db, admin, module.id, RosterAdd(user_ids=[p.id for p in five])
    )

    for person in five:
        assert [m.id for m in module_service.list_for(db, person)] == [module.id]


def test_someone_already_registered_is_skipped_silently(db, admin, module, five):
    """No duplicate row, and no error raised: the person selecting fifteen names
    does not care that two were already there."""
    registration_service.register_many(db, admin, module.id, RosterAdd(user_ids=[five[0].id]))

    added = registration_service.register_many(
        db, admin, module.id, RosterAdd(user_ids=[p.id for p in five])
    )

    assert added == 4
    assert len(registration_service.roster(db, admin, module.id)) == 5


def test_the_database_refuses_a_duplicate_even_if_the_service_were_bypassed(db, module, five):
    db.add(
        Registration(user_id=five[0].id, module_id=module.id, role_in_module="trainee")
    )
    db.commit()

    db.add(
        Registration(user_id=five[0].id, module_id=module.id, role_in_module="trainee")
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_removing_one_leaves_the_others(db, admin, module, five):
    registration_service.register_many(
        db, admin, module.id, RosterAdd(user_ids=[p.id for p in five])
    )

    registration_service.remove(db, admin, module.id, five[0].id)

    assert len(registration_service.roster(db, admin, module.id)) == 4
    assert module_service.list_for(db, five[0]) == []
    for person in five[1:]:
        assert [m.id for m in module_service.list_for(db, person)] == [module.id]


def test_an_instructor_may_register_people_on_their_own_module(db, make_user, module, five):
    instructor = make_user(email="i@example.com", role="instructor")
    db.add(
        Registration(user_id=instructor.id, module_id=module.id, role_in_module="instructor")
    )
    db.commit()

    added = registration_service.register_many(
        db, instructor, module.id, RosterAdd(user_ids=[five[0].id])
    )
    assert added == 1


def test_an_instructor_may_not_touch_another_modules_roster(db, make_user, module, five):
    outsider = make_user(email="other@example.com", role="instructor")

    with pytest.raises(module_service.NotFound):
        registration_service.roster(db, outsider, module.id)

    with pytest.raises(module_service.NotFound):
        registration_service.register_many(
            db, outsider, module.id, RosterAdd(user_ids=[five[0].id])
        )


def test_a_trainee_may_not_see_the_roster(db, admin, module, five):
    registration_service.register_many(db, admin, module.id, RosterAdd(user_ids=[five[0].id]))

    with pytest.raises(module_service.NotPermitted):
        registration_service.roster(db, five[0], module.id)


def test_candidates_excludes_people_already_on_the_module(db, admin, module, five):
    before = len(registration_service.candidates(db, admin, module.id))
    registration_service.register_many(db, admin, module.id, RosterAdd(user_ids=[five[0].id]))
    after = len(registration_service.candidates(db, admin, module.id))

    assert after == before - 1


def test_a_registration_carries_no_status(db, admin, module, five):
    """It exists, or the person is not on the module (FR-030)."""
    registration_service.register_many(db, admin, module.id, RosterAdd(user_ids=[five[0].id]))
    row = db.get(Registration, registration_service.roster(db, admin, module.id)[0].id)

    assert not hasattr(row, "status")
    assert not hasattr(row, "state")
