"""Putting people on modules, and taking them off.

Nobody does either to themselves. There is no route that registers or
deregisters the acting person, and no service function that would serve one
(FR-028).
"""

from __future__ import annotations

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models.registration import Registration
from app.models.user import User
from app.schemas.module import RegistrationRead, RosterAdd
from app.services import module_service


def roster(db: DbSession, actor: User, module_id: int) -> list[RegistrationRead]:
    """Everyone on the module and in what capacity. Refused for a module the
    caller does not run (FR-029)."""
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
    """Accounts not yet on this module, for the multi-select."""
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
    """One transaction for the whole selection.

    Anyone already registered is **skipped silently**: the person doing this
    picked fifteen names and does not care that two were already there. Telling
    them is noise, not information (research R8, FR-027).
    """
    module_service.get_for_write(db, module_id, actor)

    already = {
        row.user_id
        for row in db.exec(
            select(Registration).where(Registration.module_id == module_id)
        ).all()
    }

    added = 0
    for user_id in data.user_ids:
        if user_id in already:
            continue
        if db.get(User, user_id) is None:
            continue
        db.add(
            Registration(
                user_id=user_id, module_id=module_id, role_in_module=data.role_in_module
            )
        )
        already.add(user_id)
        added += 1

    db.commit()
    return added


def remove(db: DbSession, actor: User, module_id: int, user_id: int) -> None:
    """The row goes. Attempts made later, once Phase 2 creates them, are not
    deleted; they simply stop being reachable by that person."""
    module_service.get_for_write(db, module_id, actor)

    row = db.exec(
        select(Registration).where(
            Registration.module_id == module_id, Registration.user_id == user_id
        )
    ).first()
    if row is not None:
        db.delete(row)
        db.commit()


def modules_for_trainee(db: DbSession, user: User) -> list[int]:
    """Module ids this person holds a trainee registration on."""
    rows = db.exec(
        select(Registration).where(
            Registration.user_id == user.id, Registration.role_in_module == "trainee"
        )
    ).all()
    return [row.module_id for row in rows]
