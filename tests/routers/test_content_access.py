"""Who may author, and what a draft looks like from outside.

403 for an instructor on somebody else's module; 404 for a trainee asking after
a draft (FR-018, SC-005, SC-007).
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
def owner(db, make_user, module):
    person = make_user(email="owner@example.com", role="instructor")
    db.add(
        Registration(user_id=person.id, module_id=module.id, role_in_module="instructor")
    )
    db.commit()
    return person


@pytest.fixture()
def draft(db, owner, module):
    return content_service.create_page(
        db, owner, module.id, PageWrite(title="Unfinished", body="<p>later</p>")
    )


@pytest.fixture()
def live(db, owner, module):
    page = content_service.create_page(
        db, owner, module.id, PageWrite(title="Ready", body="<p>read me</p>")
    )
    content_service.set_page_published(db, owner, module.id, page.id, True)
    return page


AUTHORING_PATHS = ["/pages", "/pages/new"]


@pytest.mark.parametrize("suffix", AUTHORING_PATHS)
def test_an_instructor_on_another_module_is_refused(
    client, make_user, sign_in, module, suffix
):
    sign_in(make_user(email="other@example.com", role="instructor"))
    # They cannot see the module at all, so it does not exist as far as they know.
    assert client.get(f"/modules/{module.id}{suffix}").status_code == 404


@pytest.mark.parametrize("suffix", AUTHORING_PATHS)
def test_a_registered_trainee_may_not_author(
    client, db, make_user, sign_in, module, suffix
):
    trainee = make_user(email="t@example.com", role="trainee")
    db.add(Registration(user_id=trainee.id, module_id=module.id, role_in_module="trainee"))
    db.commit()
    sign_in(trainee)

    assert client.get(f"/modules/{module.id}{suffix}").status_code == 403


def test_a_trainee_gets_404_for_a_draft_page(client, db, make_user, sign_in, module, draft):
    trainee = make_user(email="t@example.com", role="trainee")
    db.add(Registration(user_id=trainee.id, module_id=module.id, role_in_module="trainee"))
    db.commit()
    sign_in(trainee)

    assert client.get(f"/modules/{module.id}/pages/{draft.id}").status_code == 404


def test_a_trainee_reads_a_published_page(client, db, make_user, sign_in, module, live):
    trainee = make_user(email="t@example.com", role="trainee")
    db.add(Registration(user_id=trainee.id, module_id=module.id, role_in_module="trainee"))
    db.commit()
    sign_in(trainee)

    response = client.get(f"/modules/{module.id}/pages/{live.id}")
    assert response.status_code == 200
    assert "read me" in response.text


def test_the_owner_sees_both(client, sign_in, module, owner, draft, live):
    sign_in(owner)

    listing = client.get(f"/modules/{module.id}/pages")
    assert listing.status_code == 200
    assert "Unfinished" in listing.text
    assert "Ready" in listing.text


def test_an_outsider_cannot_upload_to_the_module(client, make_user, sign_in, module, csrf):
    sign_in(make_user(email="other@example.com", role="instructor"))

    response = client.post(
        f"/modules/{module.id}/images",
        data={"csrf_token": csrf("/modules")},
        files={"file": ("x.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    assert response.status_code == 404
