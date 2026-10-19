"""Module cover helpers in app/art.py."""

from __future__ import annotations

import pytest

from app import art


# ------------------------------------------------------------- the vocabulary


def test_nothing_is_drawn_any_more():
    """Only colours and uploads are supported."""
    for gone in ("PATTERNS", "TILED", "LABELS", "DESCRIPTIONS", "derive"):
        assert not hasattr(art, gone), f"art.{gone} should have been removed"


def test_there_are_eight_colours():
    assert len(art.COLOURS) == 8
    assert len(set(art.COLOURS)) == 8


# ---------------------------------------------------------------- the colour


def test_every_module_has_a_colour():
    """Every module id gets a colour."""
    for module_id in range(0, 50):
        assert art.colour_for(module_id) in art.COLOURS


def test_a_missing_id_still_gives_a_colour():
    assert art.colour_for(None) in art.COLOURS
    assert art.colour_for(0) in art.COLOURS


def test_the_colour_is_stable_for_a_given_module():
    """The default colour is the same each time."""
    assert art.colour_for(7) == art.colour_for(7)


def test_neighbouring_modules_differ():
    """Consecutive ids get different colours."""
    assert len({art.colour_for(n) for n in range(1, 9)}) == 8


# ------------------------------------------------------------ a picked colour


def test_a_picked_colour_is_the_one_worn():
    """A picked colour is used instead of the default."""
    for name in art.COLOURS:
        assert art.parse_colour(name, module_id=3) == name


def test_nothing_picked_falls_back_to_the_id():
    assert art.parse_colour(None, module_id=3) == art.colour_for(3)
    assert art.parse_colour("", module_id=3) == art.colour_for(3)


def test_a_colour_outside_the_palette_falls_back_rather_than_breaking():
    """An unknown colour falls back to the default."""
    for bad in ("puce", "#ff0000", "red", "TEAL", "teal.green"):
        assert art.parse_colour(bad, module_id=3) == art.colour_for(3)


def test_an_uploaded_cover_falls_back_for_its_colour():
    """An uploaded cover uses the default colour underneath."""
    stored = art.format_upload("0123456789abcdef0123456789abcdef.png")

    assert art.parse_colour(stored, module_id=3) == art.colour_for(3)


def test_a_colour_round_trips():
    assert art.parse_colour(art.format_colour("teal"), module_id=9) == "teal"


def test_formatting_refuses_a_colour_outside_the_palette():
    for bad in ("puce", "", "#ff0000"):
        with pytest.raises(art.InvalidArt):
            art.format_colour(bad)


def test_a_stored_colour_is_not_an_upload():
    """A colour value is not treated as an upload."""
    for name in art.COLOURS:
        assert art.uploaded(name) is None


# ---------------------------------------------------------- uploaded covers


def test_no_value_means_no_picture():
    assert art.uploaded(None) is None
    assert art.uploaded("") is None


def test_a_value_left_over_from_the_drawn_covers_means_no_picture():
    """Old pattern values like `uqud.green` are treated as no upload."""
    for stale in ("uqud.green", "shield.teal", "firewall.amber", "diamonds.sky"):
        assert art.uploaded(stale) is None


def test_an_upload_value_gives_back_the_file_name():
    name = "0123456789abcdef0123456789abcdef.png"
    assert art.uploaded(f"upload.{name}") == name


def test_a_name_the_platform_did_not_generate_is_refused():
    """Names that don't match the generated format are rejected."""
    for bad in (
        "upload.../../etc/passwd",
        "upload./etc/passwd",
        "upload.not-a-uuid.png",
        "upload.0123456789abcdef0123456789abcdef",          # no extension
        "upload.0123456789ABCDEF0123456789ABCDEF.png",      # not lower case
        "upload.",
        "upload",
    ):
        assert art.uploaded(bad) is None, bad


# --------------------------------------------------------------- formatting


def test_a_stored_name_round_trips():
    name = "0123456789abcdef0123456789abcdef.jpg"

    assert art.format_upload(name) == f"upload.{name}"
    assert art.uploaded(art.format_upload(name)) == name


def test_formatting_refuses_the_shapes_reading_refuses():
    for bad in ("../x.png", "x.png", "", "0123456789abcdef0123456789abcdef"):
        with pytest.raises(art.InvalidArt):
            art.format_upload(bad)


def test_the_stored_value_fits_the_column():
    """The stored value fits in VARCHAR(64)."""
    longest = art.format_upload("0123456789abcdef0123456789abcdef.jpeg")
    assert len(longest) <= 64
