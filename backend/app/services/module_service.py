"""Modules, instructor assignment and module access checks.

All module access goes through `get_for`, which raises `NotFound` both when the
module doesn't exist and when the user can't see it.
"""

from __future__ import annotations

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.database import utcnow
from app import art
from app.models.module import Module
from app.models.registration import Registration
from app.models.user import User
from app.schemas.module import ModuleRead, ModuleWrite


class NotFound(Exception):
    """Module doesn't exist or the user can't see it."""


class NotPermitted(Exception):
    """The user can see the module but not edit it."""


# ---------------------------------------------------------------- access


def get_for(db: DbSession, module_id: int, actor: User) -> Module:
    """Get a module the user can see.

    Admin: any module. Instructor: assigned modules. Trainee: published modules
    they are registered on. Deleted modules are hidden from everyone.
    """
    module = db.get(Module, module_id)
    if module is None or module.deleted_at is not None:
        raise NotFound()

    if actor.role == "administrator":
        return module

    registration = _registration(db, module_id, actor.id)
    if registration is None:
        raise NotFound()

    if registration.role_in_module == "instructor":
        return module

    # A trainee sees it only once it is published.
    if not module.is_published:
        raise NotFound()
    return module


def get_for_write(db: DbSession, module_id: int, actor: User) -> Module:
    """Get a module the user can edit (admin or assigned instructor).

    404 if they can't see it, 403 if they can see it but not edit it.
    """
    module = get_for(db, module_id, actor)
    if actor.role == "administrator":
        return module

    registration = _registration(db, module_id, actor.id)
    if registration is None or registration.role_in_module != "instructor":
        raise NotPermitted()
    return module


def _registration(db: DbSession, module_id: int, user_id: int) -> Registration | None:
    return db.exec(
        select(Registration).where(
            Registration.module_id == module_id, Registration.user_id == user_id
        )
    ).first()


# ------------------------------------------------------------------- listing


def list_for(db: DbSession, actor: User) -> list[ModuleRead]:
    """Modules visible to the user (depends on role)."""
    live = select(Module).where(Module.deleted_at.is_(None)).order_by(Module.title)

    if actor.role == "administrator":
        return [ModuleRead.of(row) for row in db.exec(live).all()]

    mine = db.exec(
        select(Registration).where(Registration.user_id == actor.id)
    ).all()
    by_module = {row.module_id: row.role_in_module for row in mine}
    if not by_module:
        return []

    rows = db.exec(live.where(Module.id.in_(by_module.keys()))).all()
    return [
        ModuleRead.of(row)
        for row in rows
        if by_module[row.id] == "instructor" or row.is_published
    ]


# ---------------------------------------------------- administrator-only writes


def require_administrator(actor: User) -> None:
    if actor.role != "administrator":
        raise NotPermitted()


def create(db: DbSession, actor: User, data: ModuleWrite) -> ModuleRead:
    require_administrator(actor)
    # Null if no colour was picked (the default colour is used).
    row = Module(
        title=data.title.strip(),
        description=data.description,
        art=art.format_colour(data.art_colour) if data.art_colour else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ModuleRead.of(row)


def update(db: DbSession, actor: User, module_id: int, data: ModuleWrite) -> ModuleRead:
    require_administrator(actor)
    row = get_for(db, module_id, actor)
    row.title = data.title.strip()
    row.description = data.description

    # Only change the cover if a colour was submitted.
    if data.art_colour:
        row.art = art.format_colour(data.art_colour)

    db.add(row)
    db.commit()
    db.refresh(row)
    return ModuleRead.of(row)


def set_art(db: DbSession, actor: User, module_id: int, value: str | None) -> ModuleRead:
    """Set the module's `art` column (admin only). Used by content_service."""
    require_administrator(actor)
    row = get_for(db, module_id, actor)
    row.art = value
    db.add(row)
    db.commit()
    db.refresh(row)
    return ModuleRead.of(row)


def set_published(db: DbSession, actor: User, module_id: int, published: bool) -> ModuleRead:
    require_administrator(actor)
    row = get_for(db, module_id, actor)
    row.is_published = published
    db.add(row)
    db.commit()
    db.refresh(row)
    return ModuleRead.of(row)


def soft_delete(db: DbSession, actor: User, module_id: int) -> None:
    """Soft delete a module. Related data is kept so it can be restored."""
    require_administrator(actor)
    row = get_for(db, module_id, actor)
    row.deleted_at = utcnow()
    db.add(row)
    db.commit()


def restore(db: DbSession, actor: User, module_id: int) -> ModuleRead:
    require_administrator(actor)
    row = db.get(Module, module_id)
    if row is None:
        raise NotFound()
    row.deleted_at = None
    db.add(row)
    db.commit()
    db.refresh(row)
    return ModuleRead.of(row)


# ------------------------------------------------------------------ instructors


def assign_instructor(db: DbSession, actor: User, module_id: int, user_id: int) -> None:
    """Assign an instructor to a module."""
    require_administrator(actor)
    get_for(db, module_id, actor)

    existing = _registration(db, module_id, user_id)
    if existing is not None:
        existing.role_in_module = "instructor"
        db.add(existing)
    else:
        db.add(
            Registration(user_id=user_id, module_id=module_id, role_in_module="instructor")
        )
    db.commit()


def remove_instructor(db: DbSession, actor: User, module_id: int, user_id: int) -> None:
    """Remove an instructor. Pages they wrote stay in the module."""
    require_administrator(actor)
    get_for(db, module_id, actor)

    existing = _registration(db, module_id, user_id)
    if existing is not None and existing.role_in_module == "instructor":
        db.delete(existing)
        db.commit()
