"""Finding and reading your training.

The dashboard lists exactly the modules the trainee is registered on, and this
is the same page Phase 3 extends with a state. There is no second list
(FR-031, FR-014, SC-005, SC-006).
"""

from __future__ import annotations

import pytest

from app.models.module import Module
from app.models.registration import Registration
from app.schemas.module import PageWrite
from app.services import content_service


@pytest.fixture()
def modules(db):
    rows = []
    for title in ("Phishing", "Passwords", "Devices"):
        row = Module(title=title, is_published=True)
        db.add(row)
        rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


@pytest.fixture()
def owner(db, make_user, modules):
    person = make_user(email="owner@example.com", role="instructor")
    for module in modules:
        db.add(
            Registration(
                user_id=person.id, module_id=module.id, role_in_module="instructor"
            )
        )
    db.commit()
    return person


@pytest.fixture()
def trainee(db, make_user, modules):
    person = make_user(email="t@example.com", role="trainee")
    # Registered on the first two only.
    for module in modules[:2]:
        db.add(
            Registration(user_id=person.id, module_id=module.id, role_in_module="trainee")
        )
    db.commit()
    return person


def test_the_dashboard_lists_their_modules_and_no_others(client, sign_in, trainee, modules):
    sign_in(trainee)
    page = client.get("/")

    assert page.status_code == 200
    assert "Phishing" in page.text
    assert "Passwords" in page.text
    assert "Devices" not in page.text


def test_a_module_they_are_not_on_is_unreachable_by_address(
    client, sign_in, trainee, modules
):
    sign_in(trainee)
    assert client.get(f"/modules/{modules[2].id}").status_code == 404


def test_published_pages_appear_in_the_instructors_order(
    client, db, sign_in, owner, trainee, modules
):
    module = modules[0]
    for title in ("Third", "First", "Second"):
        content_service.create_page(
            db, owner, module.id, PageWrite(title=title, body=f"<p>{title}</p>")
        )

    pages = content_service.list_pages(db, owner, module.id)
    for page in pages:
        content_service.set_page_published(db, owner, module.id, page.id, True)
    content_service.reorder(
        db, owner, module.id, [pages[1].id, pages[2].id, pages[0].id]
    )

    sign_in(trainee)
    home = client.get(f"/modules/{module.id}")

    assert home.status_code == 200
    order = [home.text.index(title) for title in ("First", "Second", "Third")]
    assert order == sorted(order), "pages must appear in the instructor's order"


def test_a_draft_leaves_no_trace_in_the_trainees_view(
    client, db, sign_in, owner, trainee, modules
):
    module = modules[0]
    content_service.create_page(
        db, owner, module.id, PageWrite(title="SecretDraft", body="<p>x</p>")
    )

    sign_in(trainee)
    home = client.get(f"/modules/{module.id}")

    assert "SecretDraft" not in home.text


def test_an_empty_module_is_not_an_error(client, sign_in, trainee, modules):
    sign_in(trainee)
    home = client.get(f"/modules/{modules[0].id}")

    assert home.status_code == 200
    assert "no readable pages" in home.text.lower()


def test_a_trainee_with_no_registrations_is_told_so(client, make_user, sign_in):
    sign_in(make_user(email="lonely@example.com", role="trainee"))
    page = client.get("/")

    assert page.status_code == 200
    assert "not on any modules" in page.text.lower()


def test_the_dashboard_is_the_only_list_of_a_trainees_modules(client, sign_in, trainee):
    """Phase 3 extends this page rather than adding a second one, so /modules and
    the dashboard must agree rather than diverge."""
    sign_in(trainee)

    dashboard = client.get("/")
    listing = client.get("/modules")

    for title in ("Phishing", "Passwords"):
        assert title in dashboard.text
        assert title in listing.text
    assert "Devices" not in listing.text
