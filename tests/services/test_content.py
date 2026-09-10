"""Pages: drafts, order, publishing one at a time, and a body that is not cut.

The sanitising rule has its own module; this one is about the mechanics
(FR-012, FR-013, FR-017, SC-011).
"""

from __future__ import annotations

import pytest

from app.models.module import Module
from app.models.registration import Registration
from app.schemas.module import PageWrite
from app.services import content_service


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


@pytest.fixture()
def trainee(db, make_user, module):
    person = make_user(email="t@example.com", role="trainee")
    db.add(Registration(user_id=person.id, module_id=module.id, role_in_module="trainee"))
    db.commit()
    return person


def _page(db, instructor, module, title, published=False):
    page = content_service.create_page(
        db, instructor, module.id, PageWrite(title=title, body=f"<p>{title}</p>")
    )
    if published:
        content_service.set_page_published(db, instructor, module.id, page.id, True)
    return page


# ------------------------------------------------------------------- creating


def test_a_new_page_is_a_draft_positioned_last(db, instructor, module):
    first = _page(db, instructor, module, "One")
    second = _page(db, instructor, module, "Two")

    assert first.is_published is False
    assert second.is_published is False
    assert (first.position, second.position) == (1, 2)


def test_a_page_needs_a_title():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PageWrite(title="   ", body="<p>x</p>")


# ------------------------------------------------------------------ reordering


def test_reordering_rewrites_positions_and_keeps_them_unique(db, instructor, module):
    one = _page(db, instructor, module, "One")
    two = _page(db, instructor, module, "Two")
    three = _page(db, instructor, module, "Three")

    content_service.reorder(db, instructor, module.id, [three.id, one.id, two.id])

    pages = content_service.list_pages(db, instructor, module.id)
    assert [p.title for p in pages] == ["Three", "One", "Two"]
    assert [p.position for p in pages] == [1, 2, 3]


def test_reordering_twice_settles(db, instructor, module):
    one = _page(db, instructor, module, "One")
    two = _page(db, instructor, module, "Two")

    content_service.reorder(db, instructor, module.id, [two.id, one.id])
    content_service.reorder(db, instructor, module.id, [one.id, two.id])

    pages = content_service.list_pages(db, instructor, module.id)
    assert [p.title for p in pages] == ["One", "Two"]


# ------------------------------------------------------------------ publishing


def test_publishing_acts_on_one_page_alone(db, instructor, module, trainee):
    _page(db, instructor, module, "One", published=True)
    _page(db, instructor, module, "Two", published=True)
    _page(db, instructor, module, "Three")

    readable = content_service.list_readable(db, trainee, module.id)
    assert [p.title for p in readable] == ["One", "Two"]

    everything = content_service.list_pages(db, instructor, module.id)
    assert len(everything) == 3


def test_a_draft_is_absent_from_a_trainees_view(db, instructor, module, trainee):
    draft = _page(db, instructor, module, "Secret")

    assert content_service.list_readable(db, trainee, module.id) == []
    with pytest.raises(content_service.PageNotFound):
        content_service.get_page(db, trainee, module.id, draft.id)


def test_unpublishing_hides_a_page_but_keeps_it_editable(db, instructor, module, trainee):
    page = _page(db, instructor, module, "One", published=True)
    content_service.set_page_published(db, instructor, module.id, page.id, False)

    assert content_service.list_readable(db, trainee, module.id) == []
    assert content_service.get_page(db, instructor, module.id, page.id).title == "One"


# -------------------------------------------------------------------- deleting


def test_deleting_a_page_removes_it(db, instructor, module):
    page = _page(db, instructor, module, "One")
    content_service.delete_page(db, instructor, module.id, page.id)

    assert content_service.list_pages(db, instructor, module.id) == []


# ------------------------------------------------------------------- long body


def test_a_five_thousand_word_body_survives_intact(db, instructor, module):
    """MEDIUMTEXT, not TEXT: MySQL cuts a TEXT column at 64KB silently."""
    words = " ".join(f"word{n}" for n in range(5000))
    body = f"<p>{words}</p>"

    page = content_service.create_page(
        db, instructor, module.id, PageWrite(title="Long", body=body)
    )
    stored = content_service.get_page(db, instructor, module.id, page.id)

    assert len(stored.body) > 64 * 1024 or "word4999" in stored.body
    assert "word0" in stored.body
    assert "word4999" in stored.body
