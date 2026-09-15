"""Pages, their order, image uploads, and a module's cover picture.

Two rules carry this module. **`sanitise` runs before every write of `body`,
never after**, so the column cannot hold anything unsafe. And `save_image` takes
file **bytes and a filename**, not an `UploadFile`: reading the upload off the
request is the router's job, and everything after it is plain arguments
(Principle II).
"""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlmodel import Session as DbSession
from sqlmodel import select

from app import art
from app.config import settings
from app.database import utcnow
from app.models.content_image import ContentImage
from app.models.page import Page
from app.models.user import User
from app.sanitise import sanitise
from app.schemas.module import (
    ImageRead,
    ModuleRead,
    PageRead,
    PageSummary,
    PageWrite,
)
from app.services import module_service


class PageNotFound(Exception):
    pass


class UploadRejected(Exception):
    """Wrong type or too large. The message says which, and names the limit."""


# ----------------------------------------------------------------------- pages


def list_pages(db: DbSession, actor: User, module_id: int) -> list[PageSummary]:
    """Everything, drafts included. For the instructor's page list."""
    module_service.get_for_write(db, module_id, actor)
    rows = db.exec(
        select(Page).where(Page.module_id == module_id).order_by(Page.position)
    ).all()
    return [PageSummary.of(row) for row in rows]


def list_readable(db: DbSession, actor: User, module_id: int) -> list[PageSummary]:
    """Published pages only, in the instructor's order (FR-014).

    A draft is absent from a trainee's view entirely, with no sign it exists.
    """
    module_service.get_for(db, module_id, actor)
    rows = db.exec(
        select(Page)
        .where(Page.module_id == module_id, Page.is_published == True)  # noqa: E712
        .order_by(Page.position)
    ).all()
    return [PageSummary.of(row) for row in rows]


def get_page(db: DbSession, actor: User, module_id: int, page_id: int) -> PageRead:
    """A draft is 404 for anyone who may not write to the module."""
    module_service.get_for(db, module_id, actor)
    row = _page(db, module_id, page_id)

    if not row.is_published:
        try:
            module_service.get_for_write(db, module_id, actor)
        except module_service.NotPermitted:
            raise PageNotFound() from None
    return PageRead.of(row)


def create_page(db: DbSession, actor: User, module_id: int, data: PageWrite) -> PageRead:
    """Created as a draft, positioned last."""
    module_service.get_for_write(db, module_id, actor)

    row = Page(
        module_id=module_id,
        title=data.title.strip(),
        body=sanitise(data.body),
        position=_next_position(db, module_id),
        is_published=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return PageRead.of(row)


def update_page(
    db: DbSession, actor: User, module_id: int, page_id: int, data: PageWrite
) -> PageRead:
    """Last write wins. `updated_at` records who won, not that a conflict
    happened (spec, Assumptions)."""
    module_service.get_for_write(db, module_id, actor)

    row = _page(db, module_id, page_id)
    row.title = data.title.strip()
    row.body = sanitise(data.body)
    row.updated_at = utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)
    return PageRead.of(row)


def set_page_published(
    db: DbSession, actor: User, module_id: int, page_id: int, published: bool
) -> PageRead:
    module_service.get_for_write(db, module_id, actor)
    row = _page(db, module_id, page_id)
    row.is_published = published
    db.add(row)
    db.commit()
    db.refresh(row)
    return PageRead.of(row)


def delete_page(db: DbSession, actor: User, module_id: int, page_id: int) -> None:
    """Its images stay on the volume, unreferenced. Nothing collects orphans."""
    module_service.get_for_write(db, module_id, actor)
    row = _page(db, module_id, page_id)
    db.delete(row)
    db.commit()


def reorder(db: DbSession, actor: User, module_id: int, order: list[int]) -> None:
    """Rewrite the affected positions in one transaction, keeping them unique
    within the module (research R5, FR-013).

    Written in two passes because `(module_id, position)` is unique: moving a
    page onto a position another page still holds would collide.
    """
    module_service.get_for_write(db, module_id, actor)

    rows = {
        row.id: row
        for row in db.exec(select(Page).where(Page.module_id == module_id)).all()
    }
    wanted = [page_id for page_id in order if page_id in rows]

    for offset, page_id in enumerate(wanted):
        rows[page_id].position = -(offset + 1)
        db.add(rows[page_id])
    db.flush()

    for offset, page_id in enumerate(wanted):
        rows[page_id].position = offset + 1
        db.add(rows[page_id])
    db.commit()


def _next_position(db: DbSession, module_id: int) -> int:
    rows = db.exec(select(Page).where(Page.module_id == module_id)).all()
    return max((row.position for row in rows), default=0) + 1


def _page(db: DbSession, module_id: int, page_id: int) -> Page:
    row = db.get(Page, page_id)
    if row is None or row.module_id != module_id:
        raise PageNotFound()
    return row


# ---------------------------------------------------------------------- images


def validate_upload(content: bytes, filename: str) -> str:
    """Refuse an upload, or return the extension it will be stored under.

    Separate from writing it so a caller can refuse a file before doing
    anything else. Creating a module and only then discovering its picture is
    a spreadsheet would leave the module made and the person confused about
    which half of the form succeeded.
    """
    extension = Path(filename or "").suffix.lower()
    if extension not in settings.allowed_image_extensions:
        allowed = ", ".join(settings.allowed_image_extensions)
        raise UploadRejected(f"Only image files are accepted: {allowed}")

    if len(content) > settings.upload_max_bytes:
        actual = len(content) / (1024 * 1024)
        raise UploadRejected(
            f"That file is {actual:.1f}MB. The limit is {settings.upload_max_mb}MB."
        )

    return extension


def _store_upload(content: bytes, filename: str) -> str:
    """Check one upload and write it; return the name it was given.

    The stored name is generated. That is not extra hardening: it is what stops
    a filename like `../../app/main.py` deciding where the file lands.
    """
    extension = validate_upload(content, filename)

    stored_name = f"{uuid.uuid4().hex}{extension}"
    directory = Path(settings.upload_dir)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / stored_name).write_bytes(content)
    return stored_name


def _discard_upload(db: DbSession, module_id: int, stored_name: str) -> None:
    """Remove one stored file and the row that described it.

    Only a name this platform generated is ever unlinked: `art.uploaded` is the
    same shape check the column is written through, so a value that arrived by
    any other route names nothing on disk and nothing is deleted.
    """
    if art.uploaded(f"{art.UPLOAD}{art.SEPARATOR}{stored_name}") is None:
        return

    (Path(settings.upload_dir) / stored_name).unlink(missing_ok=True)

    row = db.exec(
        select(ContentImage).where(
            ContentImage.module_id == module_id,
            ContentImage.stored_name == stored_name,
        )
    ).first()
    if row is not None:
        db.delete(row)
        db.commit()


def save_image(
    db: DbSession,
    actor: User,
    module_id: int,
    content: bytes,
    filename: str,
) -> ImageRead:
    """Bytes and a filename, never an `UploadFile` (Principle II).

    The stored name is generated. That is not extra hardening: it is what stops
    a filename like `../../app/main.py` deciding where the file lands.
    """
    module_service.get_for_write(db, module_id, actor)

    stored_name = _store_upload(content, filename)

    row = ContentImage(
        module_id=module_id,
        stored_name=stored_name,
        original_name=(filename or stored_name)[:255],
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return ImageRead(
        id=row.id, url=f"/uploads/{stored_name}", original_name=row.original_name
    )


# ----------------------------------------------------------------- the cover


def set_cover(
    db: DbSession,
    actor: User,
    module_id: int,
    content: bytes,
    filename: str,
) -> ModuleRead:
    """Put an uploaded picture on a module in place of its plain colour.

    The permission is checked before a byte is written, so a caller who could
    not have saved the module never leaves a file behind on the volume.

    A picture it replaces is deleted, file and row together. Nothing else in
    the platform collects an orphaned image, and this is the one place that
    knows for certain which file stopped being a cover.
    """
    module_service.require_administrator(actor)
    module = module_service.get_for(db, module_id, actor)
    previous = art.uploaded(module.art)

    stored_name = _store_upload(content, filename)

    db.add(
        ContentImage(
            module_id=module_id,
            stored_name=stored_name,
            original_name=(filename or stored_name)[:255],
        )
    )
    db.commit()

    result = module_service.set_art(
        db, actor, module_id, art.format_upload(stored_name)
    )

    if previous and previous != stored_name:
        _discard_upload(db, module_id, previous)

    return result


def clear_cover(db: DbSession, actor: User, module_id: int) -> ModuleRead:
    """Take the picture off, leaving the module its plain colour.

    The column goes back to null, and `art.colour_for` then gives the module
    the same colour it wore before any picture was put on it. Nothing is
    remembered because nothing was ever chosen.
    """
    module_service.require_administrator(actor)
    module = module_service.get_for(db, module_id, actor)
    previous = art.uploaded(module.art)
    if previous is None:
        return ModuleRead.of(module)

    result = module_service.set_art(db, actor, module_id, None)
    _discard_upload(db, module_id, previous)
    return result
