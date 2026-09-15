"""Every module carries a cover, and it is the same cover everywhere.

Nothing is drawn. A module wears a picture its administrator uploaded, or a
colour: the one picked for it, or one derived from its id when nobody picked.
What is worth asserting is exactly that: a module always has a cover, the same
one on every page, and modules nobody chose for do not look alike.
"""

from __future__ import annotations

import re

import pytest

from sqlmodel import select

from app import art
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


def test_a_module_without_a_picture_requests_no_file(client, sign_in, admin, modules):
    """A colour costs no request. A module with no uploaded picture must not
    leave a broken image box behind, and nothing is fetched from a CDN."""
    sign_in(admin)
    page = client.get("/modules")

    assert "<img" not in page.text
    assert "http://" not in page.text.replace("http://www.w3.org", "")


def test_the_module_table_gained_exactly_one_column(engine):
    """The whole cover in one nullable column, holding an uploaded file name
    or nothing at all."""
    from sqlalchemy import inspect

    columns = {c["name"] for c in inspect(engine).get_columns("module")}
    assert columns == {
        "id", "title", "description", "is_published", "created_at", "deleted_at",
        # One nullable column holds the whole cover. The colour is not in it:
        # it comes from the id, so the two can never disagree.
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


# ------------------------------------------------------------- the picker


def test_the_form_offers_every_colour(client, sign_in, admin):
    from app import art

    sign_in(admin)
    page = client.get("/modules/new").text

    for name in art.COLOURS:
        assert f'value="{name}"' in page


def test_the_picker_shows_the_colours_themselves(client, sign_in, admin):
    """Not a dropdown of words: "violet" in a list tells you nothing about what
    the card will look like."""
    from app import art

    sign_in(admin)
    page = client.get("/modules/new").text

    assert page.count("colour-swatch") >= len(art.COLOURS)


def test_a_picked_colour_is_stored_and_shown(client, db, sign_in, admin, csrf):
    sign_in(admin)

    client.post(
        "/modules",
        data={
            "title": "Picked",
            "description": "",
            "art_colour": "rose",
            "csrf_token": csrf("/modules/new"),
        },
    )

    row = db.exec(select(Module).where(Module.title == "Picked")).first()
    assert row.art == "rose"
    assert "module-art module-art-rose" in client.get(f"/modules/{row.id}").text


def test_a_module_created_without_picking_stores_nothing(client, db, sign_in, admin, csrf):
    """The id decides instead, and storing a derived colour would let the two
    disagree the moment either changed."""
    sign_in(admin)

    client.post(
        "/modules",
        data={"title": "Unpicked", "description": "", "csrf_token": csrf("/modules/new")},
    )

    row = db.exec(select(Module).where(Module.title == "Unpicked")).first()
    assert row.art is None
    assert f"module-art module-art-{art.colour_for(row.id)}" in client.get("/modules").text


def test_the_edit_form_comes_back_with_the_current_colour(client, db, sign_in, admin):
    row = Module(title="Edit Me", art="violet")
    db.add(row)
    db.commit()
    db.refresh(row)
    sign_in(admin)

    page = client.get(f"/modules/{row.id}/edit").text

    assert 'value="violet"' in page
    assert 'value="violet"\n                   checked' in page or "checked" in page


def test_a_crafted_colour_is_refused(client, db, sign_in, admin, csrf):
    """The picker offers eight, and the service refuses anything else rather
    than trusting that the form was the only way in."""
    sign_in(admin)

    response = client.post(
        "/modules",
        data={
            "title": "Crafted",
            "description": "",
            "art_colour": "puce",
            "csrf_token": csrf("/modules/new"),
        },
    )

    assert response.status_code == 400
    assert db.exec(select(Module).where(Module.title == "Crafted")).first() is None
