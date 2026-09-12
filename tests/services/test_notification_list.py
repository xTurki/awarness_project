"""The list, the indicator, and what marks them seen."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.database import utcnow
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
    """Write notifications directly: this module is about reading them."""

    def _told(person, title: str, minutes_ago: int = 0, kind: str = "overdue", due_date=None):
        row = Notification(
            user_id=person.id,
            module_id=module.id,
            kind=kind,
            title=title,
            body=f"About {title}",
            due_date=due_date,
            created_at=utcnow() - timedelta(minutes=minutes_ago),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    return _told


# ------------------------------------------------------------------ the list


def test_the_list_is_newest_first(db, make_user, told):
    person = make_user(email="a@example.com")
    told(person, "Oldest", minutes_ago=30, due_date=utcnow().date())
    told(person, "Middle", minutes_ago=20, kind="due_soon", due_date=utcnow().date())
    told(person, "Newest", minutes_ago=10, kind="registered")

    rows = notification_service.list_for(db, person)

    assert [row.title for row in rows] == ["Newest", "Middle", "Oldest"]


def test_each_entry_names_its_module_and_links_to_it(db, make_user, told, module):
    person = make_user(email="a@example.com")
    told(person, "Overdue: Phishing Awareness")

    row = notification_service.list_for(db, person)[0]

    assert row.module_title == "Phishing Awareness"
    assert row.link == f"/modules/{module.id}"


def test_a_person_with_none_gets_an_empty_list_and_the_page_says_so(db, make_user):
    """The service returns nothing; the template turns that into a sentence
    rather than an empty frame."""
    assert notification_service.list_for(db, make_user(email="none@example.com")) == []


def test_one_persons_list_never_holds_anothers(db, make_user, told):
    mine = make_user(email="mine@example.com")
    theirs = make_user(email="theirs@example.com")
    told(mine, "Mine")
    told(theirs, "Theirs")

    assert [row.title for row in notification_service.list_for(db, mine)] == ["Mine"]


# ------------------------------------------------------------- the indicator


def test_the_count_is_of_what_has_not_been_seen(db, make_user, told):
    person = make_user(email="a@example.com")
    told(person, "One", kind="registered")
    told(person, "Two", kind="result")

    assert notification_service.unread_count(db, person) == 2


def test_opening_the_list_marks_everything_shown_as_seen(db, make_user, told):
    person = make_user(email="a@example.com")
    told(person, "One", kind="registered")
    told(person, "Two", kind="result")

    notification_service.mark_seen(db, person)

    assert notification_service.unread_count(db, person) == 0
    assert all(row.is_seen for row in notification_service.list_for(db, person))


def test_marking_seen_touches_nobody_elses(db, make_user, told):
    mine = make_user(email="mine@example.com")
    theirs = make_user(email="theirs@example.com")
    told(mine, "Mine")
    told(theirs, "Theirs")

    notification_service.mark_seen(db, mine)

    assert notification_service.unread_count(db, theirs) == 1


def test_something_new_arriving_afterwards_raises_the_indicator_again(
    db, make_user, told
):
    person = make_user(email="a@example.com")
    told(person, "One", kind="registered")
    notification_service.mark_seen(db, person)

    told(person, "Two", kind="result")

    assert notification_service.unread_count(db, person) == 1
