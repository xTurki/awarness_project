"""An uploaded picture as a module's cover, in place of its plain colour.

The picture is a field of the module form, saved by the same button as the
title. That is what these tests hold in place: there is one Save, it works on a
module that does not exist yet, and a save that attaches no file leaves the
picture where it is.

The cover lives in one column that holds a file name or nothing, so the rest
of what is worth pinning is what that column makes possible to get wrong: that
saving does not throw the picture away, that replacing one does not leave the
old file behind, and that removing one leaves a cover rather than a gap.

Every test points `upload_dir` at a temporary directory, so a run never writes
to the real volume and never depends on what is already on it.
"""

from __future__ import annotations

import pytest
from sqlmodel import select

from app import art
from app.config import settings
from app.models.module import Module


PNG = b"\x89PNG\r\n\x1a\n" + b"pretend this is an image" * 4

#: What a browser posts for a file input nobody touched: the part is there,
#: with no filename and no bytes.
EMPTY_FIELD = {"cover": ("", b"", "application/octet-stream")}


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch):
    """A disposable uploads directory for the whole test."""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.fixture()
def admin(make_user):
    return make_user(email="admin@example.com", role="administrator")


@pytest.fixture()
def module(db):
    row = Module(title="Phishing Awareness", is_published=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _save(client, csrf, module, *, title=None, files=None, **fields):
    """Save the module form, the way the browser does: one multipart post."""
    data = {
        "title": title if title is not None else module.title,
        "description": "",
        "csrf_token": csrf(f"/modules/{module.id}/edit"),
        **fields,
    }
    return client.post(f"/modules/{module.id}", data=data, files=files or EMPTY_FIELD)


def _picture(name="cover.png", content=PNG):
    return {"cover": (name, content, "image/png")}


def _art(db, module_id: int) -> str | None:
    db.expire_all()
    return db.get(Module, module_id).art


def _stored(db, module_id: int) -> str | None:
    return art.uploaded(_art(db, module_id))


# ------------------------------------------------------- one form, one Save


def test_the_form_carries_the_file_field_and_saves_it_with_everything_else(
    client, sign_in, admin, module
):
    """Two save buttons on one page is two ways to half-save it, so the picture
    is a field of this form and has no button of its own."""
    sign_in(admin)
    page = client.get(f"/modules/{module.id}/edit").text

    assert 'enctype="multipart/form-data"' in page
    assert 'name="cover"' in page
    assert "Save changes" in page
    assert "Upload picture" not in page


def test_an_untouched_file_field_is_accepted_as_a_browser_sends_it(
    client, db, sign_in, csrf, admin, module
):
    """A browser posts the empty input with `filename=""` rather than leaving
    the filename out, which is a different shape on the wire from the one the
    helper above produces. Both have to be read as "no picture", so this builds
    the browser's shape by hand."""
    sign_in(admin)
    token = csrf(f"/modules/{module.id}/edit")
    boundary = "----pytestboundary"

    crlf = "\r\n"

    def part(name, value, filename=None):
        head = f'Content-Disposition: form-data; name="{name}"'
        if filename is not None:
            head += f'; filename="{filename}"'
            head += crlf + "Content-Type: application/octet-stream"
        return f"--{boundary}{crlf}{head}{crlf}{crlf}{value}{crlf}"

    body = (
        part("title", "Renamed by a browser")
        + part("description", "")
        + part("csrf_token", token)
        + part("cover", "", filename="")
        + f"--{boundary}--{crlf}"
    ).encode()

    response = client.post(
        f"/modules/{module.id}",
        content=body,
        headers={"content-type": f"multipart/form-data; boundary={boundary}"},
    )

    assert response.status_code in (200, 303)
    assert db.get(Module, module.id).title == "Renamed by a browser"


def test_a_new_module_can_be_given_a_picture_as_it_is_created(
    client, db, sign_in, csrf, admin, uploads
):
    """The whole reason the field is in this form: there is no second step."""
    sign_in(admin)

    response = client.post(
        "/modules",
        data={
            "title": "Device Security",
            "description": "",
            "csrf_token": csrf("/modules/new"),
        },
        files=_picture(),
    )

    assert response.status_code in (200, 303)
    made = db.exec(
        select(Module).where(Module.title == "Device Security")
    ).first()
    stored = art.uploaded(made.art)
    assert stored is not None
    assert (uploads / stored).read_bytes() == PNG


def test_a_new_module_without_a_picture_stores_no_cover(
    client, db, sign_in, csrf, admin
):
    """The field is optional, and an untouched one must not be read as a file.
    Nothing is stored: the module wears the colour its id gives it."""
    sign_in(admin)

    client.post(
        "/modules",
        data={
            "title": "Passwords",
            "description": "",
            "csrf_token": csrf("/modules/new"),
        },
        files=EMPTY_FIELD,
    )

    made = db.exec(
        select(Module).where(Module.title == "Passwords")
    ).first()
    assert made.art is None


# ------------------------------------------------------------------ uploading


def test_a_picture_becomes_the_cover(client, db, sign_in, csrf, admin, module, uploads):
    sign_in(admin)

    response = _save(client, csrf, module, files=_picture())

    assert response.status_code in (200, 303)
    stored = _stored(db, module.id)
    assert stored is not None
    assert (uploads / stored).read_bytes() == PNG


def test_the_module_page_shows_the_picture(
    client, db, sign_in, csrf, admin, module
):
    sign_in(admin)
    _save(client, csrf, module, files=_picture())

    page = client.get(f"/modules/{module.id}")

    assert f'src="/uploads/{_stored(db, module.id)}"' in page.text


def test_the_cover_is_the_same_picture_in_the_list(
    client, db, sign_in, csrf, admin, module
):
    """One cover, everywhere. A card showing a plain colour while the module
    page showed a photograph would read as two different modules."""
    sign_in(admin)
    _save(client, csrf, module, files=_picture())

    assert f'src="/uploads/{_stored(db, module.id)}"' in client.get("/modules").text


# ------------------------------------------------- saving must not lose it


def test_saving_without_choosing_a_file_keeps_the_picture(
    client, db, sign_in, csrf, admin, module, uploads
):
    """The commonest save there is: change the title, touch nothing else. The
    empty file field must not be read as an upload."""
    sign_in(admin)
    _save(client, csrf, module, files=_picture())
    before = _art(db, module.id)

    _save(client, csrf, module, title="Phishing Awareness, revised")

    assert _art(db, module.id) == before
    assert (uploads / _stored(db, module.id)).exists()
    assert db.get(Module, module.id).title == "Phishing Awareness, revised"


def test_the_form_offers_to_remove_a_picture_in_use(
    client, sign_in, csrf, admin, module
):
    """And the picture itself is shown, so the person removing it can see what
    they are removing."""
    sign_in(admin)
    _save(client, csrf, module, files=_picture())

    form = client.get(f"/modules/{module.id}/edit").text

    assert "Remove this picture" in form
    assert 'name="remove_cover"' in form
    assert "/uploads/" in form


# --------------------------------------------------------- replacing, removing


def test_replacing_a_picture_deletes_the_one_it_replaced(
    client, db, sign_in, csrf, admin, module, uploads
):
    """Nothing else in the platform collects an orphaned image, so a module
    whose cover changed ten times would otherwise leave ten files behind."""
    sign_in(admin)
    _save(client, csrf, module, files=_picture())
    first = _stored(db, module.id)

    _save(client, csrf, module, files=_picture("second.png", PNG + b"different"))
    second = _stored(db, module.id)

    assert second != first
    assert not (uploads / first).exists()
    assert (uploads / second).exists()


def test_ticking_remove_takes_the_picture_off_and_deletes_the_file(
    client, db, sign_in, csrf, admin, module, uploads
):
    sign_in(admin)
    _save(client, csrf, module, files=_picture())
    stored = _stored(db, module.id)

    _save(client, csrf, module, remove_cover="yes")

    assert not (uploads / stored).exists()
    assert _art(db, module.id) is None


def test_removing_a_picture_leaves_a_cover_behind(
    client, db, sign_in, csrf, admin, module
):
    """A module never renders an empty box. With the column back to null the
    cover is derived from the id, which is what it was before anyone chose."""
    sign_in(admin)
    _save(client, csrf, module, files=_picture())
    _save(client, csrf, module, remove_cover="yes")

    page = client.get(f"/modules/{module.id}")

    assert "module-art module-art-" in page.text
    assert "/uploads/" not in page.text


def test_the_column_is_empty_again_once_the_picture_is_gone(
    client, db, sign_in, csrf, admin, module
):
    """Null, not a leftover value: the colour comes from the id, so there is
    nothing else the column could honestly hold."""
    sign_in(admin)
    _save(client, csrf, module, files=_picture())
    _save(client, csrf, module, remove_cover="yes")

    assert _art(db, module.id) is None


def test_a_new_file_wins_over_a_ticked_remove(
    client, db, sign_in, csrf, admin, module
):
    """Choosing a replacement and ticking remove in the same save is a
    contradiction. The file is the more deliberate of the two."""
    sign_in(admin)
    _save(client, csrf, module, files=_picture())

    _save(client, csrf, module, files=_picture("new.png", PNG + b"new"),
          remove_cover="yes")

    assert _stored(db, module.id) is not None


# ------------------------------------------------------------------ refusals


def test_a_file_that_is_not_an_image_is_refused_in_words(
    client, db, sign_in, csrf, admin, module
):
    """As a page with the reason at the top, the way a missing title is
    refused, and not as a body of JSON."""
    sign_in(admin)

    response = _save(client, csrf, module, files=_picture("notes.txt", b"text"))

    assert response.status_code == 400
    assert "Only image files are accepted" in response.text
    assert "<form" in response.text
    assert _art(db, module.id) is None


def test_a_file_over_the_limit_is_refused_and_names_the_limit(
    client, db, sign_in, csrf, admin, module, monkeypatch
):
    monkeypatch.setattr(settings, "upload_max_mb", 1)
    sign_in(admin)

    response = _save(
        client, csrf, module, files=_picture(content=b"x" * (2 * 1024 * 1024))
    )

    assert response.status_code == 400
    assert "The limit is 1MB" in response.text
    assert _art(db, module.id) is None


def test_a_refused_picture_does_not_create_the_module(
    client, db, sign_in, csrf, admin, uploads
):
    """Checked before the module is made, so a rejected picture does not leave
    a module behind that nobody asked for."""
    sign_in(admin)

    response = client.post(
        "/modules",
        data={
            "title": "Should Not Exist",
            "description": "",
            "csrf_token": csrf("/modules/new"),
        },
        files=_picture("notes.txt", b"text"),
    )

    assert response.status_code == 400
    assert db.exec(
        select(Module).where(Module.title == "Should Not Exist")
    ).first() is None
    assert list(uploads.iterdir()) == []


def test_a_refused_picture_leaves_nothing_on_the_volume(
    client, sign_in, csrf, admin, module, uploads
):
    sign_in(admin)

    _save(client, csrf, module, files=_picture("notes.txt", b"text"))

    assert list(uploads.iterdir()) == []


def test_a_refused_title_does_not_take_the_picture_with_it(
    client, db, sign_in, csrf, admin, module, uploads
):
    sign_in(admin)
    _save(client, csrf, module, files=_picture())
    stored = _stored(db, module.id)

    response = _save(client, csrf, module, title="   ")

    assert response.status_code == 400
    assert (uploads / stored).exists()
    assert _stored(db, module.id) == stored


# ---------------------------------------------------------------- who may


def test_an_instructor_cannot_reach_the_module_form_at_all(
    client, db, sign_in, csrf, make_user, module, uploads
):
    """The cover is part of the module record, and only an administrator edits
    that."""
    sign_in(make_user(email="teacher@example.com", role="instructor"))

    response = client.post(
        f"/modules/{module.id}",
        data={"title": "Taken over", "description": ""},
        files=_picture(),
    )

    assert response.status_code in (403, 404)
    assert _art(db, module.id) is None
    assert list(uploads.iterdir()) == []


def test_saving_without_a_csrf_token_is_refused(client, sign_in, admin, module):
    sign_in(admin)

    response = client.post(
        f"/modules/{module.id}",
        data={"title": "No token", "description": ""},
        files=_picture(),
    )

    assert response.status_code == 403


def test_signing_in_is_required(client, module):
    response = client.post(
        f"/modules/{module.id}",
        data={"title": "Nobody", "description": ""},
        files=_picture(),
    )

    assert response.status_code in (303, 403)
