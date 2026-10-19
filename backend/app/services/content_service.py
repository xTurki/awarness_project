"""Pages, page order, image uploads and module cover images.

Page bodies are always sanitised before they are saved.
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
    """Invalid file type or file too large."""


# ----------------------------------------------------------------------- pages


def list_pages(db: DbSession, actor: User, module_id: int) -> list[PageSummary]:
    """All pages including drafts (instructor view)."""
    module_service.get_for_write(db, module_id, actor)
    rows = db.exec(
        select(Page).where(Page.module_id == module_id).order_by(Page.position)
    ).all()
    return [PageSummary.of(row) for row in rows]


def list_readable(db: DbSession, actor: User, module_id: int) -> list[PageSummary]:
    """Published pages only, in order."""
    module_service.get_for(db, module_id, actor)
    rows = db.exec(
        select(Page)
        .where(Page.module_id == module_id, Page.is_published == True)  # noqa: E712
        .order_by(Page.position)
    ).all()
    return [PageSummary.of(row) for row in rows]


def get_page(db: DbSession, actor: User, module_id: int, page_id: int) -> PageRead:
    """Get a page. Drafts are 404 for users who can't edit the module."""
    module_service.get_for(db, module_id, actor)
    row = _page(db, module_id, page_id)

    if not row.is_published:
        try:
            module_service.get_for_write(db, module_id, actor)
        except module_service.NotPermitted:
            raise PageNotFound() from None
    return PageRead.of(row)


def create_page(db: DbSession, actor: User, module_id: int, data: PageWrite) -> PageRead:
    """Create a draft page at the end."""
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
    """Update a page (last write wins)."""
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
    """Delete a page. Its uploaded images are not deleted."""
    module_service.get_for_write(db, module_id, actor)
    row = _page(db, module_id, page_id)
    db.delete(row)
    db.commit()


def reorder(db: DbSession, actor: User, module_id: int, order: list[int]) -> None:
    """Move a page to a new position.

    Done in two passes because (module_id, position) is unique.
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
    """Validate an upload and return its extension. Raises UploadRejected."""
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
    """Validate and save an upload; return the generated file name.

    The name is generated so the original filename can't control the path.
    """
    extension = validate_upload(content, filename)

    stored_name = f"{uuid.uuid4().hex}{extension}"
    directory = Path(settings.upload_dir)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / stored_name).write_bytes(content)
    return stored_name


def _discard_upload(db: DbSession, module_id: int, stored_name: str) -> None:
    """Delete a stored image file and its row (only valid generated names)."""
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
    """Save an image for page content and return it.

    The name is generated so the original filename can't control the path.
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
    """Set an uploaded image as the module cover.

    Permission is checked before saving. The previous cover image is deleted.
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
    """Remove the cover image; the module goes back to its default colour."""
    module_service.require_administrator(actor)
    module = module_service.get_for(db, module_id, actor)
    previous = art.uploaded(module.art)
    if previous is None:
        return ModuleRead.of(module)

    result = module_service.set_art(db, actor, module_id, None)
    _discard_upload(db, module_id, previous)
    return result
