"""Every module carries a cover, and it is the same cover everywhere.

The artwork is drawn from the module id rather than stored, which is why this
feature needed no column, no upload route, and no change to the database. What
is worth asserting is exactly that: a module always has one, the same one on
every page, and modules differ from each other.
"""

from __future__ import annotations

import re

import pytest

from app.models.module import Module
from app.models.registration import Registration


@pytest.fixture()
def admin(make_user):
    return make_user(email="admin@example.com", role="administrator")


@pytest.fixture()
def modules(db):
    rows = [Module(title=title, is_published=True)
            for title in ("Phishing", "Passwords", "Devices", "Email", "Travel",
                          "Reporting", "Backups")]
    for row in rows:
        db.add(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def _covers(html: str) -> list[str]:
    """Every cover rendered on the page, as its colour class."""
    return re.findall(r"module-art module-art-([a-z]+)", html)


# ------------------------------------------------------------ always present


def test_every_module_card_carries_artwork(client, sign_in, admin, modules):
    sign_in(admin)
    page = client.get("/modules")

    assert page.status_code == 200
    assert len(_covers(page.text)) == len(modules)


def test_the_module_page_carries_it_too(client, sign_in, admin, modules):
    sign_in(admin)
    page = client.get(f"/modules/{modules[0].id}")

    assert page.status_code == 200
    assert "module-art-tall" in page.text


def test_a_module_looks_the_same_on_every_page(client, sign_in, admin, modules):
    """A cover that changed between the list and the page would be decoration
    rather than identity."""
    sign_in(admin)

    listed = client.get("/modules").text
    home = client.get(f"/modules/{modules[0].id}").text

    on_home = re.search(r"module-art module-art-([a-z]+)", home).group(1)
    assert f"module-art-{on_home}" in listed


def test_it_survives_a_reload(client, sign_in, admin, modules):
    sign_in(admin)

    first = _covers(client.get("/modules").text)
    second = _covers(client.get("/modules").text)

    assert first == second, "artwork must not be picked at random"


# ------------------------------------------------------------------ variety


def test_neighbouring_modules_do_not_look_alike(client, sign_in, admin, modules):
    """Seven modules with nothing chosen, falling back on their ids."""
    sign_in(admin)
    covers = _covers(client.get("/modules").text)

    assert len(set(covers)) == 7


def test_the_colour_is_always_one_from_the_vocabulary(client, sign_in, admin, modules):
    from app import art

    sign_in(admin)
    for value in _covers(client.get("/modules").text):
        assert value in art.COLOURS


# --------------------------------------------------------- the trainee view


def test_a_trainee_sees_it_on_their_own_dashboard(client, db, sign_in, make_user, modules):
    person = make_user(email="t@example.com", role="trainee")
    db.add(Registration(user_id=person.id, module_id=modules[0].id,
                        role_in_module="trainee"))
    db.commit()
    sign_in(person)

    page = client.get(f"/modules/{modules[0].id}")

    assert page.status_code == 200
    assert "module-art" in page.text


# -------------------------------------------------------------- the promise


def test_no_picture_is_ever_fetched_from_anywhere(client, sign_in, admin, modules):
    """Drawn in the page, so a module with no uploaded image is not a broken
    image box, and nothing is requested from a CDN."""
    sign_in(admin)
    page = client.get("/modules")

    assert "<img" not in page.text
    assert "http://" not in page.text.replace("http://www.w3.org", "")


def test_the_module_table_gained_exactly_one_column(engine):
    """The whole cover, pattern and colour, in one nullable column."""
    from sqlalchemy import inspect

    columns = {c["name"] for c in inspect(engine).get_columns("module")}
    assert columns == {
        "id", "title", "description", "is_published", "created_at", "deleted_at",
        # One nullable column holds the whole cover, so adding it to a live
        # database needed one ALTER and no backfill.
        "art",
    }


# ------------------------------------------------------------ asset freshness


def test_the_stylesheet_url_carries_a_version(client):
    """Without this, a cache in front of the platform serves the previous
    stylesheet until its TTL expires. On the live deployment that is four
    hours, which looks exactly like a change that failed to deploy."""
    page = client.get("/login")

    assert "/static/css/app.css?v=" in page.text


def test_the_version_changes_with_the_stylesheet(tmp_path, monkeypatch):
    """A digest of the files, so an unchanged deploy keeps the cached copy and
    a changed one cannot be served from it."""
    from app import rendering

    before = rendering._asset_version()
    monkeypatch.setattr(rendering, "_STATIC", tmp_path)
    (tmp_path / "css").mkdir()
    (tmp_path / "css" / "app.css").write_text("body { color: red }")

    assert rendering._asset_version() != before


# --------------------------------------------------------------- the picker


def test_the_form_offers_every_pattern_and_colour(client, sign_in, admin):
    """Built from the same lists the service validates against, so the form
    cannot offer something that would then be refused."""
    from app import art

    sign_in(admin)
    page = client.get("/modules/new")

    for name in art.PATTERNS:
        assert f'value="{name}"' in page.text
    for name in art.COLOURS:
        assert f'value="{name}"' in page.text


def test_the_picker_shows_the_patterns_themselves(client, sign_in, admin):
    """Not a dropdown of words: "Uqud" in a list tells you nothing about
    what the card will look like."""
    sign_in(admin)
    page = client.get("/modules/new")

    assert page.text.count("module-art-swatch") >= 14


def test_choosing_a_cover_is_stored_and_rendered(client, db, sign_in, admin, csrf):
    from app.models.module import Module

    sign_in(admin)
    token = csrf("/modules/new")
    response = client.post(
        "/modules",
        data={
            "title": "Chosen Cover",
            "description": "",
            "art_pattern": "shurfat",
            "art_colour": "teal",
            "csrf_token": token,
        },
    )
    assert response.status_code == 303

    from sqlmodel import select

    row = db.exec(select(Module).where(Module.title == "Chosen Cover")).first()
    assert row.art == "shurfat.teal"

    page = client.get(f"/modules/{row.id}")
    assert "module-art-teal" in page.text


def test_the_edit_form_comes_back_with_the_current_cover(client, db, sign_in, admin, csrf):
    from app.models.module import Module

    row = Module(title="Edit Me", art="uqud.rose")
    db.add(row)
    db.commit()
    db.refresh(row)
    sign_in(admin)

    page = client.get(f"/modules/{row.id}/edit")

    assert 'value="uqud"' in page.text
    assert "module-art-rose" in page.text


def test_a_crafted_pattern_is_refused(client, sign_in, admin, csrf):
    """The vocabulary is enforced in the input model, not by the select box."""
    sign_in(admin)

    token = csrf("/modules/new")
    response = client.post(
        "/modules",
        data={
            "title": "Bad Cover",
            "art_pattern": "octagons",
            "art_colour": "teal",
            "csrf_token": token,
        },
    )

    assert response.status_code == 400


def test_a_crafted_colour_is_refused(client, sign_in, admin, csrf):
    sign_in(admin)

    token = csrf("/modules/new")
    response = client.post(
        "/modules",
        data={
            "title": "Bad Cover",
            "art_pattern": "shurfat",
            "art_colour": "puce",
            "csrf_token": token,
        },
    )

    assert response.status_code == 400
