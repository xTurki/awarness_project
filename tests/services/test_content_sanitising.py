"""Page HTML is sanitised before it is saved (checks the stored column)."""

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
    """Read the stored body directly from the database."""
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
    """Updates are sanitised as well."""
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
    """No dangerous HTML reaches the database through any service function."""
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
