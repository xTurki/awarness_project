"""Modules, the instructors assigned to them, and the one authorisation
chokepoint every module-scoped action in this phase and in Phases 2 to 4 passes
through.

`get_for` returns the module or raises `NotFound`. It never returns "found but
forbidden", because that would disclose that the module exists. One function
means one place to get the rule right; twenty separate checks would mean twenty
chances to forget one, and the forgotten one is the hole (research R1, FR-009).
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
    """No such module, or none this caller may see. Deliberately the same."""


class NotPermitted(Exception):
    """The caller may see the module but may not change it."""


# ---------------------------------------------------------------- the chokepoint


def get_for(db: DbSession, module_id: int, actor: User) -> Module:
    """Administrator: every module in any state.
    Instructor: modules they are assigned to, including unpublished ones.
    Trainee: published modules they hold a registration on.
    A soft-deleted module is invisible to everyone.
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
    """`module:write`: an administrator, or an instructor assigned to it.

    Resolving through `get_for` first is what keeps the 404-versus-403 rule
    honest: a caller who may not see the module is told it does not exist,
    and a caller who may see it but not change it is refused.
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
    """The list differs by role, and that is the whole point (FR-006/007/008)."""
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
    # Null when no colour was picked, and then the id decides. Storing a
    # derived colour would let the column and the id disagree later.
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

    # Only when the form offered the picker. A module wearing an uploaded
    # picture submits no colour, and its picture survives the save.
    if data.art_colour:
        row.art = art.format_colour(data.art_colour)

    db.add(row)
    db.commit()
    db.refresh(row)
    return ModuleRead.of(row)


def set_art(db: DbSession, actor: User, module_id: int, value: str | None) -> ModuleRead:
    """Write the cover column, whatever kind of cover it names.

    Here rather than in `content_service` because the permission belongs with
    the module record: only an administrator edits a module, and the cover is
    part of that record. `content_service` owns the file and calls this for the
    column, which keeps the import going one way.
    """
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
    """Reversible. Pages, images, and registrations are untouched, so restoring
    returns everything (FR-010, SC-012)."""
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
    """A module with no instructor is permitted; an administrator can assign a
    replacement at any time (FR-004)."""
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
    """They lose access immediately, including to pages they wrote. The pages
    remain with the module (spec, Edge Cases)."""
    require_administrator(actor)
    get_for(db, module_id, actor)

    existing = _registration(db, module_id, user_id)
    if existing is not None and existing.role_in_module == "instructor":
        db.delete(existing)
        db.commit()
