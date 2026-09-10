"""Sanitising happens before storage.

Every assertion here reads **the stored column**, not a rendered page. Asserting
on the render would pass even if the sanitiser were in the wrong place, which is
exactly the mistake this test exists to catch (FR-016, SC-004).
"""

from __future__ import annotations

import pytest
from sqlmodel import select

from app.models.module import Module
from app.models.page import Page
from app.models.registration import Registration
from app.schemas.module import PageWrite
from app.services import content_service

PAYLOAD = (
    "<p>Hello</p>"
    "<script>alert(1)</script>"
    '<a href="javascript:alert(2)">click</a>'
    '<img src=x onerror="alert(3)">'
)


@pytest.fixture()
def module(db):
    row = Module(title="Phishing Awareness", is_published=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture()
def instructor(db, make_user, module):
    person = make_user(email="i@example.com", role="instructor")
    db.add(
        Registration(user_id=person.id, module_id=module.id, role_in_module="instructor")
    )
    db.commit()
    return person


def _stored_body(db, page_id: int) -> str:
    """Read the column directly. No service, no template, no filter."""
    return db.exec(select(Page).where(Page.id == page_id)).first().body


def test_a_script_is_absent_from_the_stored_column(db, instructor, module):
    page = content_service.create_page(
        db, instructor, module.id, PageWrite(title="Payload", body=PAYLOAD)
    )

    stored = _stored_body(db, page.id).lower()

    assert "<script" not in stored
    assert "alert(1)" not in stored
    assert "onerror" not in stored
    assert "javascript:" not in stored


def test_the_harmless_part_is_still_there(db, instructor, module):
    page = content_service.create_page(
        db, instructor, module.id, PageWrite(title="Payload", body=PAYLOAD)
    )
    assert "<p>Hello</p>" in _stored_body(db, page.id)


def test_editing_sanitises_too(db, instructor, module):
    """Not only creation. An edit is a write, and every write is sanitised."""
    page = content_service.create_page(
        db, instructor, module.id, PageWrite(title="Clean", body="<p>fine</p>")
    )
    content_service.update_page(
        db, instructor, module.id, page.id, PageWrite(title="Clean", body=PAYLOAD)
    )

    stored = _stored_body(db, page.id).lower()
    assert "<script" not in stored
    assert "onerror" not in stored


def test_nothing_dangerous_can_reach_the_column_by_any_service_route(db, instructor, module):
    """Belt and braces: whatever goes in, the column comes out clean."""
    for payload in [
        "<iframe src='//evil'></iframe>",
        "<form action='/admin/accounts'><button>x</button></form>",
        "<style>body{display:none}</style>",
        "<p onmouseover='alert(1)'>hover</p>",
    ]:
        page = content_service.create_page(
            db, instructor, module.id, PageWrite(title="P", body=payload)
        )
        stored = _stored_body(db, page.id).lower()

        assert "<iframe" not in stored
        assert "<form" not in stored
        assert "<style" not in stored
        assert "onmouseover" not in stored
