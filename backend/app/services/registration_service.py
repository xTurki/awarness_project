"""Registering users on modules and removing them."""

from __future__ import annotations

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models.module import Module
from app.models.registration import Registration
from app.models.user import User
from app.schemas.module import RegistrationRead, RosterAdd
from app.services import module_service, notification_service


def roster(db: DbSession, actor: User, module_id: int) -> list[RegistrationRead]:
    """Everyone registered on the module (requires edit access)."""
    module_service.get_for_write(db, module_id, actor)

    rows = db.exec(
        select(Registration, User)
        .join(User, User.id == Registration.user_id)
        .where(Registration.module_id == module_id)
        .order_by(User.full_name)
    ).all()

    return [
        RegistrationRead(
            id=registration.id,
            user_id=registration.user_id,
            module_id=registration.module_id,
            role_in_module=registration.role_in_module,
            registered_at=registration.registered_at,
            full_name=person.full_name,
            email=person.email,
        )
        for registration, person in rows
    ]


def candidates(db: DbSession, actor: User, module_id: int) -> list[User]:
    """Active users not yet registered on the module."""
    module_service.get_for_write(db, module_id, actor)

    already = {
        row.user_id
        for row in db.exec(
            select(Registration).where(Registration.module_id == module_id)
        ).all()
    }
    people = db.exec(
        select(User).where(User.is_active == True).order_by(User.full_name)  # noqa: E712
    ).all()
    return [person for person in people if person.id not in already]


def register_many(db: DbSession, actor: User, module_id: int, data: RosterAdd) -> int:
    """Register several users in one transaction. Existing ones are skipped."""
    module_service.get_for_write(db, module_id, actor)

    # Only admins can add instructors; instructors can only add trainees.
    if data.role_in_module == "instructor" and actor.role != "administrator":
        raise module_service.NotPermitted(
            "Only an administrator can assign an instructor to a module."
        )

    already = {
        row.user_id
        for row in db.exec(
            select(Registration).where(Registration.module_id == module_id)
        ).all()
    }

    registered: list[User] = []
    for user_id in data.user_ids:
        if user_id in already:
            continue
        person = db.get(User, user_id)
        if person is None:
            continue
        db.add(
            Registration(
                user_id=user_id, module_id=module_id, role_in_module=data.role_in_module
            )
        )
        already.add(user_id)
        registered.append(person)

    db.commit()

    # Notify each new user now. Email failures don't undo the registration.
    module = db.get(Module, module_id)
    for person in registered:
        notification_service.notify_registered(db, person, module)

    return len(registered)


def remove(db: DbSession, actor: User, module_id: int, user_id: int) -> None:
    """Remove a registration. The user's attempts are kept."""
    module_service.get_for_write(db, module_id, actor)

    row = db.exec(
        select(Registration).where(
            Registration.module_id == module_id, Registration.user_id == user_id
        )
    ).first()
    if row is not None:
        db.delete(row)
        db.commit()

