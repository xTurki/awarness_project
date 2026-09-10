"""Image uploads.

The stored name is generated. That is not extra hardening: it is what stops a
filename deciding where the file lands (research R3, FR-019, FR-021).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import settings
from app.models.module import Module
from app.models.registration import Registration
from app.services import content_service

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


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


@pytest.fixture(autouse=True)
def temporary_upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


# ------------------------------------------------------------------ accepted


def test_an_image_is_stored_and_returns_a_url(db, instructor, module, temporary_upload_dir):
    image = content_service.save_image(
        db, instructor, module.id, PNG, "diagram.png", "image/png"
    )

    assert image.url.startswith("/uploads/")
    assert image.original_name == "diagram.png"
    assert len(list(Path(temporary_upload_dir).glob("*.png"))) == 1


def test_the_stored_name_is_generated_not_the_uploaded_one(
    db, instructor, module, temporary_upload_dir
):
    image = content_service.save_image(
        db, instructor, module.id, PNG, "diagram.png", "image/png"
    )
    stored = image.url.rsplit("/", 1)[-1]

    assert stored != "diagram.png"
    assert len(stored) == 32 + len(".png")


def test_a_traversing_filename_cannot_decide_where_the_file_lands(
    db, instructor, module, temporary_upload_dir
):
    image = content_service.save_image(
        db, instructor, module.id, PNG, "../../app/main.png", "image/png"
    )
    stored = image.url.rsplit("/", 1)[-1]

    assert ".." not in stored
    assert "/" not in stored
    assert (Path(temporary_upload_dir) / stored).exists()


def test_a_renamed_executable_is_accepted(db, instructor, module):
    """The recorded decision, not a defect: checking is by extension only, and
    the file lands in a directory nginx serves as static content."""
    image = content_service.save_image(
        db, instructor, module.id, b"MZ\x90\x00" * 32, "payload.png", "image/png"
    )
    assert image.url.endswith(".png")


# ------------------------------------------------------------------ refused


@pytest.mark.parametrize("name", ["notes.pdf", "sheet.xlsx", "script.js", "noextension"])
def test_a_non_image_extension_is_refused(db, instructor, module, name):
    with pytest.raises(content_service.UploadRejected) as caught:
        content_service.save_image(db, instructor, module.id, PNG, name, "application/pdf")
    assert "image" in str(caught.value).lower()


def test_an_oversized_file_is_refused_and_the_message_names_the_limit(db, instructor, module):
    too_big = b"0" * (settings.upload_max_bytes + 1)

    with pytest.raises(content_service.UploadRejected) as caught:
        content_service.save_image(db, instructor, module.id, too_big, "big.png", "image/png")

    assert str(settings.upload_max_mb) in str(caught.value)


def test_a_file_at_exactly_the_limit_is_accepted(db, instructor, module):
    at_limit = b"0" * settings.upload_max_bytes
    image = content_service.save_image(
        db, instructor, module.id, at_limit, "edge.png", "image/png"
    )
    assert image.url.endswith(".png")


# ------------------------------------------------------------- who may upload


def test_a_trainee_cannot_upload_anything(db, make_user, module):
    """No route reaches this for a trainee, and the service refuses anyway."""
    from app.services import module_service

    trainee = make_user(email="t@example.com", role="trainee")
    db.add(Registration(user_id=trainee.id, module_id=module.id, role_in_module="trainee"))
    db.commit()

    with pytest.raises(module_service.NotPermitted):
        content_service.save_image(db, trainee, module.id, PNG, "x.png", "image/png")


def test_an_instructor_on_another_module_cannot_upload(db, make_user, module):
    from app.services import module_service

    outsider = make_user(email="other@example.com", role="instructor")

    with pytest.raises(module_service.NotFound):
        content_service.save_image(db, outsider, module.id, PNG, "x.png", "image/png")
