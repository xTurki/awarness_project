"""The notification routes over HTTP.

The structural assertion is the important one: **no route takes a person**.
There is no parameter to tamper with, so FR-033 is not a guard that could be
forgotten, it is the absence of a way to ask.
"""

from __future__ import annotations

import pytest

from app.main import app
from app.models.module import Module
from app.models.notification import Notification
from app.services import notification_service


@pytest.fixture()
def module(db):
    row = Module(title="Phishing Awareness", is_published=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture()
def told(db, module):
    def _told(person, title: str, kind: str = "registered"):
        row = Notification(
            user_id=person.id, module_id=module.id, kind=kind, title=title
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    return _told


# ------------------------------------------------------------------ structure


def test_no_route_names_a_person():
    """Every notification path is the caller's own (FR-033)."""
    paths = {route.path for route in app.routes if "notification" in route.path}

    assert paths == {"/notifications", "/notifications/read"}
    for path in paths:
        assert "{" not in path, f"{path} takes a parameter"


def test_this_phase_adds_exactly_one_post():
    posts = {
        route.path
        for route in app.routes
        if "notification" in route.path and "POST" in getattr(route, "methods", set())
    }
    assert posts == {"/notifications/read"}


# --------------------------------------------------------------- the two routes


def test_the_list_shows_the_callers_own(client, sign_in, make_user, told):
    person = make_user(email="a@example.com")
    told(person, "Overdue: Phishing Awareness")
    sign_in(person)

    page = client.get("/notifications")

    assert page.status_code == 200
    assert "Overdue: Phishing Awareness" in page.text


def test_the_list_never_shows_somebody_elses(client, sign_in, make_user, told):
    mine = make_user(email="mine@example.com")
    theirs = make_user(email="theirs@example.com")
    told(mine, "Mine")
    told(theirs, "Theirs, and private")
    sign_in(mine)

    page = client.get("/notifications")

    assert "Mine" in page.text
    assert "Theirs, and private" not in page.text


def test_a_person_with_none_is_told_so(client, sign_in, make_user):
    sign_in(make_user(email="none@example.com"))
    page = client.get("/notifications")

    assert page.status_code == 200
    assert "nothing has been sent to you" in page.text.lower()


def test_signing_out_is_required(client):
    assert client.get("/notifications").status_code == 303


def test_opening_the_list_clears_the_indicator(client, db, sign_in, make_user, told):
    person = make_user(email="a@example.com")
    told(person, "Overdue: Phishing Awareness")
    sign_in(person)

    client.get("/notifications")

    assert notification_service.unread_count(db, person) == 0


def test_marking_read_without_a_csrf_token_is_refused(client, sign_in, make_user):
    sign_in(make_user(email="a@example.com"))
    assert client.post("/notifications/read").status_code == 403


def test_marking_read_clears_the_indicator(client, db, sign_in, make_user, csrf, told):
    person = make_user(email="a@example.com")
    told(person, "Overdue: Phishing Awareness")
    sign_in(person)

    token = csrf("/")
    response = client.post("/notifications/read", data={"csrf_token": token})

    assert response.status_code == 303
    assert notification_service.unread_count(db, person) == 0


# ------------------------------------------------------------- the shell badge


def test_the_shell_shows_a_count_on_every_page(client, sign_in, make_user, told):
    person = make_user(email="a@example.com")
    told(person, "One")
    told(person, "Two", kind="result")
    sign_in(person)

    for path in ("/", "/modules"):
        page = client.get(path)
        assert "Notifications" in page.text
        assert ">2<" in page.text.replace(" ", "").replace("\n", "")


def test_the_badge_is_absent_when_there_is_nothing(client, sign_in, make_user):
    sign_in(make_user(email="quiet@example.com"))
    page = client.get("/")

    assert "Notifications" in page.text
    assert "rounded-pill" not in page.text
